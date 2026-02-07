import 'package:intl/intl.dart';

class Formatters {
  static String distance(double meters) {
    if (meters < 1000) {
      return '${meters.round()}m';
    }
    return '${(meters / 1000).toStringAsFixed(1)}km';
  }

  static String discount({
    required String type,
    required double value,
  }) {
    if (type == 'percent') {
      return '${value.round()}% 할인';
    }
    return '${NumberFormat('#,###').format(value.round())}원 할인';
  }

  static String currency(double amount) {
    return '${NumberFormat('#,###').format(amount.round())}원';
  }

  static String dateTime(String isoString) {
    final dt = DateTime.parse(isoString);
    return DateFormat('yyyy.MM.dd HH:mm').format(dt);
  }

  static String date(String isoString) {
    final dt = DateTime.parse(isoString);
    return DateFormat('yyyy.MM.dd').format(dt);
  }

  static String relativeTime(String isoString) {
    final dt = DateTime.parse(isoString);
    final now = DateTime.now();
    final diff = now.difference(dt);

    if (diff.inMinutes < 1) return '방금 전';
    if (diff.inHours < 1) return '${diff.inMinutes}분 전';
    if (diff.inDays < 1) return '${diff.inHours}시간 전';
    if (diff.inDays < 30) return '${diff.inDays}일 전';
    return DateFormat('yyyy.MM.dd').format(dt);
  }
}
