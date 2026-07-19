class AppConstants {
  AppConstants._();

  // App details
  static const String appName = 'ONDC Buyer Cert';
  static const String appTitle = 'ONDC Buyer Certification';

  // API Config
  static const String apiBaseUrl = 'http://localhost:8000/api/v1';
  static const Duration apiTimeout = Duration(seconds: 30);

  // Spacing & Padding
  static const double spaceXS = 4.0;
  static const double spaceS = 8.0;
  static const double spaceM = 16.0;
  static const double spaceL = 24.0;
  static const double spaceXL = 32.0;
  static const double spaceXXL = 48.0;
  static const double space3XL = 64.0;

  // Border Radius
  static const double radiusXS = 4.0;
  static const double radiusS = 8.0;
  static const double radiusM = 12.0;
  static const double radiusL = 16.0;
  static const double radiusXL = 24.0;
  static const double radiusXXL = 32.0;

  // Animation Durations
  static const Duration durationFast = Duration(milliseconds: 200);
  static const Duration durationMedium = Duration(milliseconds: 450);
  static const Duration durationSlow = Duration(milliseconds: 800);
  static const Duration splashDuration = Duration(seconds: 3);
}
