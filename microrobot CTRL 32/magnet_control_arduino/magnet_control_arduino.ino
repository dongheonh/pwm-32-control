#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// SAM LAB, D H HAN
// 09/23/2025
// Pixel-level control for a 4×8 electromagnet array 
// This code sets per-coil **magnitude (0–100%)** and **direction (+/−)** in real time. therefore [-100, 100]

// INPUT AND OUTPUT
// INPUT: csv data (line by line) from serial 
// OUTPUT: I2C communication, send signal back to the serial (validate communication)

// Comnication: I2C, send 8 bit data to each address
// PCA9685 Output 16 PWM signals 


// Instantiate four PCA9685 drivers with different I2C addresses (hardware address) 
// change adress (nxnn) if needed
Adafruit_PWMServoDriver pwm1(0x72);
Adafruit_PWMServoDriver pwm2(0x7D);
Adafruit_PWMServoDriver pwm3(0x7C);
Adafruit_PWMServoDriver pwm4(0x78);

void setup() {
  Serial.begin(115200);  // Start serial communication

  // Initialize all PWM drivers
  pwm1.begin();
  pwm2.begin();
  pwm3.begin();
  pwm4.begin();

  delay(10);  // Small delay to ensure stability
}




void loop() {
  int nToken = 64;    // Expecting 64 integer values in [0, 10] - intensity and polarity of 32 magnets therefore 32 * 2 = 64
  int nGr = 4;        // 4 groups of 16 channels - groups by each column (4 columns and 8 rows)
  
  // control input
  int values[64];     // *** Store parsed integer values as an integer (UNO: 64 × 2 B = 128 B, PICO: 64 × 4 B = 256 B): Control Input

  // STRING -> INT
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');  // Read a line from Serial (line by line) save as a String Object
    line.trim(); // use trim method to trim line by line

    // *** Print the received CSV string to the Serial Monitor: TO VALIDATE COMMUNICATION
    Serial.println(line); // to commnication results from 


    int startIdx = 0;
    int count = 0;

    // Parse comma-separated integers
    while (count < nToken) {
      int commaIdx = line.indexOf(',', startIdx);     // find # of ',' return int (-1 return if false, ++1 return if true)
      String token;
      if (commaIdx == -1) {
        token = line.substring(startIdx);  // Last token
      } else {
        token = line.substring(startIdx, commaIdx);
      }

      token.trim();
      values[count++] = token.toInt();  // Convert string to integer, token is a String need to convert it to int

      if (commaIdx == -1) break;
      startIdx = commaIdx + 1;
    }

    // Send PWM signal to each driver
    for (int g = 0; g < nGr; g++) {
      Adafruit_PWMServoDriver* pwm;
      if (g == 0) pwm = &pwm1;        // address of pwm1
      else if (g == 1) pwm = &pwm2;   // address of pwm2
      else if (g == 2) pwm = &pwm3;   // address of pwm3
      else pwm = &pwm4;               // address of pwm4

      for (int i = 0; i < 16; i++) {
        int idx = g * 16 + i;
        int input_val = values[idx];  // Range: [0, 10]

        // for safety (optional)
        input_val = constrain(input_val, 0, 10);  // Safety: The constrain(x, a, b) function forces any input to remain within the range [a, b].

        int pwm_val = input_val * 409;  // Map 0–10 → 0–4090, PWM 0 - 100 percent
        pwm->setPWM(i, 0, pwm_val);
      }
    }
  }
}
