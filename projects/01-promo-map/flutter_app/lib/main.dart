import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';
import 'app/app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await Future.wait([
    dotenv.load(fileName: '.env.dev'),
    MobileAds.instance.initialize(),
  ]);

  runApp(
    const ProviderScope(
      child: PromoMapApp(),
    ),
  );
}
