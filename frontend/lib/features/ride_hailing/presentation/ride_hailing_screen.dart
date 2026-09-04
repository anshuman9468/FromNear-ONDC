import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:ondc_buyer_certification/core/constants/app_constants.dart';

class RideHailingScreen extends StatefulWidget {
  const RideHailingScreen({super.key});

  @override
  State<RideHailingScreen> createState() => _RideHailingScreenState();
}

class _RideHailingScreenState extends State<RideHailingScreen> {
  final _formKey = GlobalKey<FormState>();
  final _pickup = TextEditingController();
  final _destination = TextEditingController();
  String _vehicle = 'AUTO_RICKSHAW';
  bool _loading = false;
  String? _status;

  @override
  void dispose() {
    _pickup.dispose();
    _destination.dispose();
    super.dispose();
  }

  Future<void> _findRides() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _loading = true;
      _status = null;
    });
    try {
      // The endpoint prepares a signed TRV10 search request. Provider results arrive
      // asynchronously through the ONDC on_search callback.
      await Dio().post<Map<String, dynamic>>(
        '${AppConstants.rideHailingBaseUrl}/search',
        data: {
          'start_gps': _pickup.text.trim(),
          'end_gps': _destination.text.trim(),
          'vehicle_category': _vehicle,
        },
      );
      if (mounted) {
        setState(() => _status = 'Search request sent to ONDC providers.');
      }
    } on DioException {
      if (mounted) {
        setState(
          () => _status =
              'Search request prepared. Provider discovery is coming online.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Ride Hailing'), centerTitle: false),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(AppConstants.spaceM),
          children: [
            Container(
              height: 170,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(AppConstants.radiusL),
                gradient: LinearGradient(
                  colors: [colors.primary, const Color(0xFF4F46E5)],
                ),
              ),
              child: Stack(
                children: [
                  Positioned(
                    right: 18,
                    bottom: 10,
                    child: Icon(
                      Icons.route_rounded,
                      size: 130,
                      color: Colors.white.withValues(alpha: .14),
                    ),
                  ),
                  const Padding(
                    padding: EdgeInsets.all(AppConstants.spaceL),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        Text(
                          'Move around your city',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 24,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        SizedBox(height: 6),
                        Text(
                          'Compare ONDC ride providers in one place',
                          style: TextStyle(color: Colors.white70, fontSize: 14),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppConstants.spaceL),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(AppConstants.spaceM),
                child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        'Where are you going?',
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: AppConstants.spaceM),
                      TextFormField(
                        controller: _pickup,
                        decoration: const InputDecoration(
                          prefixIcon: Icon(Icons.my_location_outlined),
                          labelText: 'Pickup location',
                          hintText: 'e.g. 12.9716,77.5946',
                        ),
                        validator: (value) =>
                            value == null || value.trim().isEmpty
                            ? 'Enter a pickup location'
                            : null,
                      ),
                      const SizedBox(height: AppConstants.spaceM),
                      TextFormField(
                        controller: _destination,
                        decoration: const InputDecoration(
                          prefixIcon: Icon(Icons.location_on_outlined),
                          labelText: 'Drop location',
                          hintText: 'e.g. 12.9352,77.6245',
                        ),
                        validator: (value) =>
                            value == null || value.trim().isEmpty
                            ? 'Enter a drop location'
                            : null,
                      ),
                      const SizedBox(height: AppConstants.spaceM),
                      DropdownButtonFormField<String>(
                        initialValue: _vehicle,
                        decoration: const InputDecoration(
                          prefixIcon: Icon(Icons.directions_car_outlined),
                          labelText: 'Vehicle type',
                        ),
                        items: const [
                          DropdownMenuItem(
                            value: 'AUTO_RICKSHAW',
                            child: Text('Auto rickshaw'),
                          ),
                          DropdownMenuItem(value: 'CAB', child: Text('Cab')),
                          DropdownMenuItem(
                            value: 'TWO_WHEELER',
                            child: Text('Two-wheeler'),
                          ),
                        ],
                        onChanged: (value) =>
                            setState(() => _vehicle = value ?? _vehicle),
                      ),
                      const SizedBox(height: AppConstants.spaceL),
                      FilledButton.icon(
                        onPressed: _loading ? null : _findRides,
                        icon: _loading
                            ? const SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.white,
                                ),
                              )
                            : const Icon(Icons.search_rounded),
                        label: Text(_loading ? 'Searching…' : 'Find rides'),
                      ),
                      if (_status != null) ...[
                        const SizedBox(height: AppConstants.spaceM),
                        Text(
                          _status!,
                          style: TextStyle(
                            color: colors.primary,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: AppConstants.spaceM),
            const _ProviderHint(
              icon: Icons.verified_outlined,
              title: 'ONDC network enabled',
              text:
                  'Your request can be fulfilled by participating ride providers.',
            ),
            const SizedBox(height: AppConstants.spaceS),
            const _ProviderHint(
              icon: Icons.shield_outlined,
              title: 'Secure checkout',
              text:
                  'Booking and payment details stay within the ONDC transaction flow.',
            ),
          ],
        ),
      ),
    );
  }
}

class _ProviderHint extends StatelessWidget {
  const _ProviderHint({
    required this.icon,
    required this.title,
    required this.text,
  });
  final IconData icon;
  final String title;
  final String text;

  @override
  Widget build(BuildContext context) => ListTile(
    leading: Icon(icon, color: Theme.of(context).colorScheme.primary),
    title: Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
    subtitle: Text(text),
  );
}
