// ============================================================
//   NavHat PRO — Ultrasonic Sensor Calibration Utility
//   Board  : ESP32 Dev Module
//   Purpose: Interactive hardware calibration, noise profiling,
//            and median filter verification for HC-SR04 sensors.
// ============================================================

#define TRIG_F  13
#define ECHO_F  18
#define TRIG_L  14
#define ECHO_L  33
#define TRIG_R  19
#define ECHO_R  23

float readRaw(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  long duration = pulseIn(echoPin, HIGH, 30000);
  if (duration == 0) return 999.0f;
  return duration * 0.034f / 2.0f;
}

float readMedian(int trigPin, int echoPin) {
  float a = readRaw(trigPin, echoPin); delayMicroseconds(500);
  float b = readRaw(trigPin, echoPin); delayMicroseconds(500);
  float c = readRaw(trigPin, echoPin);

  if ((a <= b && b <= c) || (c <= b && b <= a)) return b;
  if ((b <= a && a <= c) || (c <= a && a <= b)) return a;
  return c;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n========================================================");
  Serial.println("   NavHat PRO — Sensor Calibration & Noise Profiler     ");
  Serial.println("========================================================");
  Serial.println("Format: Raw_F (cm), Filtered_F (cm), Raw_L (cm), Filtered_L (cm), Raw_R (cm), Filtered_R (cm)");

  pinMode(TRIG_F, OUTPUT); pinMode(ECHO_F, INPUT);
  pinMode(TRIG_L, OUTPUT); pinMode(ECHO_L, INPUT);
  pinMode(TRIG_R, OUTPUT); pinMode(ECHO_R, INPUT);
}

void loop() {
  float rawF = readRaw(TRIG_F, ECHO_F);
  float medF = readMedian(TRIG_F, ECHO_F);
  float rawL = readRaw(TRIG_L, ECHO_L);
  float medL = readMedian(TRIG_L, ECHO_L);
  float rawR = readRaw(TRIG_R, ECHO_R);
  float medR = readMedian(TRIG_R, ECHO_R);

  // Serial Plotter friendly CSV output
  Serial.printf("%.1f,%.1f,%.1f,%.1f,%.1f,%.1f\n", rawF, medF, rawL, medL, rawR, medR);
  delay(100);
}
