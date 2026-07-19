import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:ondc_buyer_certification/core/constants/app_constants.dart';
import 'package:ondc_buyer_certification/core/theme/app_theme.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _phoneController = TextEditingController();
  bool _isLoading = false;

  @override
  void dispose() {
    _phoneController.dispose();
    super.dispose();
  }

  void _handleLogin() {
    if (_formKey.currentState!.validate()) {
      setState(() {
        _isLoading = true;
      });

      // Simulate a login call
      Future.delayed(const Duration(seconds: 2), () {
        if (mounted) {
          setState(() {
            _isLoading = false;
          });
          context.go('/home');
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;

    return Scaffold(
      body: Row(
        children: [
          // Left Side - Branding (Visible on wide screens)
          if (MediaQuery.of(context).size.width > 800)
            Expanded(
              child: Container(
                decoration: const BoxDecoration(
                  gradient: LinearGradient(
                    colors: [Color(0xFF0F172A), Color(0xFF1E1E38)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                ),
                child: Center(
                  child: Padding(
                    padding: const EdgeInsets.all(AppConstants.spaceXL),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          padding: const EdgeInsets.all(AppConstants.spaceM),
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.08),
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(color: Colors.white.withValues(alpha: 0.12)),
                          ),
                          child: const Icon(
                            Icons.verified_user_rounded,
                            size: 40,
                            color: AppTheme.secondary,
                          ),
                        ),
                        const SizedBox(height: AppConstants.spaceXL),
                        const Text(
                          'ONDC Buyer\nCertification Platform',
                          style: TextStyle(
                            fontSize: 40,
                            fontWeight: FontWeight.w800,
                            color: Colors.white,
                            height: 1.2,
                          ),
                        ),
                        const SizedBox(height: AppConstants.spaceM),
                        Text(
                          'Sandbox testing environment for Buyer Network Participants. Configure endpoints, run test suites, and audit logs in real-time.',
                          style: TextStyle(
                            fontSize: 16,
                            color: Colors.white.withValues(alpha: 0.7),
                            height: 1.5,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          
          // Right Side - Login Panel
          Expanded(
            child: Container(
              color: colors.surface,
              child: Center(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(AppConstants.spaceXL),
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 420),
                    child: Form(
                      key: _formKey,
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          if (MediaQuery.of(context).size.width <= 800) ...[
                            Icon(
                              Icons.verified_user_rounded,
                              size: 48,
                              color: colors.primary,
                            ),
                            const SizedBox(height: AppConstants.spaceM),
                          ],
                          Text(
                            'Welcome Back',
                            style: Theme.of(context).textTheme.displayLarge?.copyWith(
                                  fontSize: 32,
                                  fontWeight: FontWeight.w800,
                                  letterSpacing: -0.5,
                                ),
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: AppConstants.spaceXS),
                          Text(
                            'Enter your phone number to access the workspace',
                            style: Theme.of(context).textTheme.bodyMedium,
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: AppConstants.spaceXXL),
                          
                          // Phone Number Field
                          Text(
                            'Phone Number',
                            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w600,
                                ),
                          ),
                          const SizedBox(height: AppConstants.spaceS),
                          TextFormField(
                            controller: _phoneController,
                            keyboardType: TextInputType.phone,
                            decoration: const InputDecoration(
                              hintText: '+91 98765 43210',
                              prefixIcon: Icon(Icons.phone_iphone_outlined),
                            ),
                            validator: (value) {
                              if (value == null || value.trim().isEmpty) {
                                return 'Please enter your phone number';
                              }
                              // Simple validation for 10 digits
                              final normalized = value.replaceAll(RegExp(r'\D'), '');
                              if (normalized.length < 10) {
                                return 'Please enter a valid 10-digit number';
                              }
                              return null;
                            },
                          ),
                          const SizedBox(height: AppConstants.spaceL),
                          
                          // Submit Button
                          ElevatedButton(
                            onPressed: _isLoading ? null : _handleLogin,
                            child: _isLoading
                                ? const SizedBox(
                                    height: 20,
                                    width: 20,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2.5,
                                      valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                                    ),
                                  )
                                : const Text('Access Sandbox'),
                          ),
                          const SizedBox(height: AppConstants.spaceXL),
                          
                          // Dummy Sandbox Info
                          Container(
                            padding: const EdgeInsets.all(AppConstants.spaceM),
                            decoration: BoxDecoration(
                              color: colors.primary.withValues(alpha: 0.05),
                              borderRadius: BorderRadius.circular(AppConstants.radiusM),
                              border: Border.all(
                                color: colors.primary.withValues(alpha: 0.1),
                                width: 1,
                              ),
                            ),
                            child: Row(
                              children: [
                                Icon(Icons.info_outline_rounded, color: colors.primary),
                                const SizedBox(width: AppConstants.spaceM),
                                const Expanded(
                                  child: Text(
                                    'This is a local environment. No real OTP is triggered for dummy authentication.',
                                    style: TextStyle(fontSize: 12),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
