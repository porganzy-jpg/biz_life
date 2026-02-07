import 'package:flutter/material.dart';
import '../../../app/constants.dart';

void showAppToast(BuildContext context, String message, {bool isError = false}) {
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(
      content: Text(message),
      backgroundColor: isError ? AppColors.error : AppColors.success,
      duration: AppDefaults.toastDuration,
    ),
  );
}
