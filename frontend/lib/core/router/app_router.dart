import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:ondc_buyer_certification/features/authentication/presentation/login_screen.dart';
import 'package:ondc_buyer_certification/features/authentication/presentation/splash_screen.dart';
import 'package:ondc_buyer_certification/features/home/presentation/home_screen.dart';

final GoRouter appRouter = GoRouter(
  initialLocation: '/',
  routes: [
    GoRoute(
      path: '/',
      name: 'splash',
      builder: (context, state) => const SplashScreen(),
    ),
    GoRoute(
      path: '/login',
      name: 'login',
      builder: (context, state) => const LoginScreen(),
    ),
    GoRoute(
      path: '/home',
      name: 'home',
      builder: (context, state) => const HomeScreen(),
    ),
  ],
  errorBuilder: (context, state) => Scaffold(
    body: Center(
      child: Text('Route not found: ${state.uri}'),
    ),
  ),
);
