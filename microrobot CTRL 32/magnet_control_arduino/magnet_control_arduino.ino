#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// SAM Lab, D. H. Han
// 04/15/2026
// Pixel-level control for a 4×8 electromagnet array
// This code sets the per-coil magnitude (0–100%) and direction (+/-) in real time.
// Therefore, the intended command range is [-100, 100].
//
// INPUT:
//   - CSV data received line by line over Serial
//
// OUTPUT:
//   - I2C commands sent to PCA9685 drivers
//   - Serial echo for communication validation
//
// Communication:
//   - I2C sends data to each PCA9685 address
//   - Each PCA9685 provides 16 PWM output channels

// Instantiate four PCA9685 drivers with different I2C addresses
// Change addresses if needed

Adafruit_PWMServoDriver pwm1(0x42); // 000010
Adafruit_PWMServoDriver pwm2(0x43); // 000011
Adafruit_PWMServoDriver pwm3(0x44); // 000100
Adafruit_PWMServoDriver pwm4(0x45); // 000101

void setup() {
  Serial.begin(115200);  // Start serial communication

  // Set I2C pins first for RP Pico
  Wire.setSDA(4);        // GP4
  Wire.setSCL(5);        // GP5
  Wire.begin();          // Initialize I2C
  Wire.setClock(400000); // Set I2C clock to 400 kHz

  // Initialize all PWM drivers
  pwm1.begin();
  pwm2.begin();
  pwm3.begin();
  pwm4.begin();

  delay(10);  // Small delay for stability
}

void loop() {
  const int nToken = 64; // Expecting 64 integer values
                        // 32 magnets × 2 values per magnet = 64
  const int nGr = 4;     // 4 PCA9685 groups, each with 16 channels

  int values[64];        // Parsed integer input values

  if (Serial.available()) {
    String line = Serial.readStringUntil('\n'); // Read one line from Serial
    line.trim();

    // Echo received CSV string for communication validation
    Serial.println(line);

    int startIdx = 0;
    int count = 0;

    // Parse comma-separated integers
    while (count < nToken) {
      int commaIdx = line.indexOf(',', startIdx);
      String token;

      if (commaIdx == -1) {
        token = line.substring(startIdx); // Last token
      } else {
        token = line.substring(startIdx, commaIdx);
      }

      token.trim();
      values[count++] = token.toInt();

      if (commaIdx == -1) break;
      startIdx = commaIdx + 1;
    }

    // Send PWM signals to each driver
    for (int g = 0; g < nGr; g++) {
      Adafruit_PWMServoDriver* pwm;

      if (g == 0)      pwm = &pwm1;
      else if (g == 1) pwm = &pwm2;
      else if (g == 2) pwm = &pwm3;
      else             pwm = &pwm4;

      for (int i = 0; i < 16; i++) {
        int idx = g * 16 + i;
        int input_val = values[idx]; // Current code assumes range [0, 10]

        // Safety clamp ㅃ
        input_val = constrain(input_val, 0, 10);

        // Map 0–10 to 0–4090
        int pwm_val = input_val * 409;

        pwm->setPWM(i, 0, pwm_val);
      }
    }
  }
}