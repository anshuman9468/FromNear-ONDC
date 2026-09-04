import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ondc_buyer_certification/features/ride_hailing/presentation/ride_hailing_screen.dart';

void main() {
  testWidgets('Ride Hailing screen renders the booking form', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: RideHailingScreen()));

    expect(find.text('Ride Hailing'), findsOneWidget);
    expect(find.text('Pickup location'), findsOneWidget);
    expect(find.text('Drop location'), findsOneWidget);
    expect(find.text('Find rides'), findsOneWidget);
  });
}
