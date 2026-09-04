import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:ondc_buyer_certification/core/constants/app_constants.dart';
import 'package:ondc_buyer_certification/core/theme/theme_provider.dart';
import 'package:ondc_buyer_certification/core/network/backend_api.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  Map<String, dynamic>? _systemStatus;
  String? _loadError;

  @override
  void initState() {
    super.initState();
    _loadStatus();
  }

  Future<void> _loadStatus() async {
    try {
      final status = await BackendApi().getSystemStatus();
      if (mounted) setState(() => _systemStatus = status);
    } catch (_) {
      if (mounted) setState(() => _loadError = 'Backend unavailable');
    }
  }

  static const Color emeraldColor = Color(0xFF10B981);

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final currentThemeMode = ref.watch(themeModeProvider);
    final database = _systemStatus?['database']?.toString() ?? 'Checking';
    final serviceState = _systemStatus?['status']?.toString() ?? 'Checking';
    final ondcConfigured = _systemStatus?['ondc']?['configured'] == true;
    final logs = <String>[
      'Backend status: $serviceState',
      'PostgreSQL: $database',
      'ONDC configuration: ${ondcConfigured ? 'Ready' : 'Incomplete'}',
      ...(_loadError == null ? const <String>[] : <String>[_loadError!]),
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Sandbox Dashboard',
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
        ),
        actions: [
          IconButton(
            icon: Icon(
              currentThemeMode == ThemeMode.dark
                  ? Icons.light_mode_outlined
                  : Icons.dark_mode_outlined,
            ),
            tooltip: 'Toggle Theme',
            onPressed: () {
              ref
                  .read(themeModeProvider.notifier)
                  .state = currentThemeMode == ThemeMode.dark
                  ? ThemeMode.light
                  : ThemeMode.dark;
            },
          ),
          IconButton(
            icon: const Icon(Icons.logout_outlined),
            tooltip: 'Logout',
            onPressed: () {
              context.go('/login');
            },
          ),
          const SizedBox(width: AppConstants.spaceS),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppConstants.spaceM),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Header Card
              Container(
                padding: const EdgeInsets.all(AppConstants.spaceL),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: Theme.of(context).brightness == Brightness.dark
                        ? [colors.primary, const Color(0xFF4F46E5)]
                        : [colors.primary, const Color(0xFF6366F1)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(AppConstants.radiusL),
                  boxShadow: [
                    BoxShadow(
                      color: colors.primary.withValues(alpha: 0.2),
                      blurRadius: 16,
                      offset: const Offset(0, 6),
                    ),
                  ],
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'ONDC Buyer Certification',
                      style: Theme.of(context).textTheme.displayLarge?.copyWith(
                        color: Colors.white,
                        fontSize: 28,
                        fontWeight: FontWeight.w900,
                        letterSpacing: -0.5,
                      ),
                    ),
                    const SizedBox(height: AppConstants.spaceS),
                    Text(
                      'Pramaan Test & Validation Environment',
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.9),
                        fontSize: 16,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    const SizedBox(height: AppConstants.spaceM),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppConstants.spaceM,
                        vertical: AppConstants.spaceS,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(
                          AppConstants.radiusS,
                        ),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: const [
                          Icon(Icons.lock_clock, color: Colors.white, size: 16),
                          SizedBox(width: AppConstants.spaceS),
                          Text(
                            'Phase 1A: Architectural Foundation Active',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppConstants.spaceL),

              Card(
                child: ListTile(
                  leading: const CircleAvatar(
                    child: Icon(Icons.local_taxi_outlined),
                  ),
                  title: const Text(
                    'Ride Hailing',
                    style: TextStyle(fontWeight: FontWeight.w700),
                  ),
                  subtitle: const Text(
                    'Book a cab, auto, or two-wheeler through ONDC',
                  ),
                  trailing: const Icon(
                    Icons.arrow_forward_ios_rounded,
                    size: 16,
                  ),
                  onTap: () => context.go('/ride-hailing'),
                ),
              ),
              const SizedBox(height: AppConstants.spaceL),

              // Diagnostics Grid
              Text(
                'System Status',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w700,
                  fontSize: 18,
                ),
              ),
              const SizedBox(height: AppConstants.spaceM),
              GridView.count(
                crossAxisCount: MediaQuery.of(context).size.width > 600 ? 3 : 1,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                childAspectRatio: 2.2,
                crossAxisSpacing: AppConstants.spaceM,
                mainAxisSpacing: AppConstants.spaceM,
                children: [
                  _buildStatusCard(
                    context,
                    title: 'FastAPI Service',
                    value: serviceState,
                    icon: Icons.cloud_done_outlined,
                    color: emeraldColor,
                  ),
                  _buildStatusCard(
                    context,
                    title: 'PostgreSQL DB',
                    value: database,
                    icon: Icons.storage_outlined,
                    color: emeraldColor,
                  ),
                  _buildStatusCard(
                    context,
                    title: 'Pramaan Suite',
                    value: ondcConfigured ? 'Ready' : 'Configure',
                    icon: Icons.check_circle_outline_rounded,
                    color: Colors.blue,
                  ),
                ],
              ),
              const SizedBox(height: AppConstants.spaceL),

              // Live Logs Console
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(AppConstants.spaceL),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'Sandbox Event logs',
                            style: Theme.of(context).textTheme.titleMedium
                                ?.copyWith(fontWeight: FontWeight.bold),
                          ),
                          Row(
                            children: [
                              Container(
                                width: 8,
                                height: 8,
                                decoration: const BoxDecoration(
                                  color: emeraldColor,
                                  shape: BoxShape.circle,
                                ),
                              ),
                              const SizedBox(width: AppConstants.spaceS),
                              const Text(
                                'Listening',
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                      const SizedBox(height: AppConstants.spaceM),
                      Container(
                        padding: const EdgeInsets.all(AppConstants.spaceM),
                        decoration: BoxDecoration(
                          color: Theme.of(context).brightness == Brightness.dark
                              ? const Color(0xFF0F172A)
                              : const Color(0xFFF1F5F9),
                          borderRadius: BorderRadius.circular(
                            AppConstants.radiusM,
                          ),
                          border: Border.all(
                            color:
                                Theme.of(context).brightness == Brightness.dark
                                ? const Color(0xFF1E293B)
                                : const Color(0xFFE2E8F0),
                          ),
                        ),
                        height: 180,
                        child: ListView.separated(
                          itemCount: logs.length,
                          separatorBuilder: (context, index) =>
                              const SizedBox(height: AppConstants.spaceS),
                          itemBuilder: (context, index) {
                            return Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  '[${DateTime.now().toLocal().toString().substring(11, 19)}] ',
                                  style: TextStyle(
                                    fontFamily: 'monospace',
                                    color: colors.primary.withValues(
                                      alpha: 0.7,
                                    ),
                                    fontSize: 13,
                                  ),
                                ),
                                Expanded(
                                  child: Text(
                                    logs[index],
                                    style: const TextStyle(
                                      fontFamily: 'monospace',
                                      fontSize: 13,
                                    ),
                                  ),
                                ),
                              ],
                            );
                          },
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatusCard(
    BuildContext context, {
    required String title,
    required String value,
    required IconData icon,
    required Color color,
  }) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppConstants.spaceM,
          vertical: AppConstants.spaceM,
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(AppConstants.spaceS),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(AppConstants.radiusM),
              ),
              child: Icon(icon, color: color, size: 28),
            ),
            const SizedBox(width: AppConstants.spaceM),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    value,
                    style: theme.textTheme.titleMedium?.copyWith(
                      color: color,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
