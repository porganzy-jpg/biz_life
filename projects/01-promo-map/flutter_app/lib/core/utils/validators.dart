class Validators {
  static String? email(String? value) {
    if (value == null || value.isEmpty) return '이메일을 입력해주세요';
    final emailRegex = RegExp(r'^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$');
    if (!emailRegex.hasMatch(value)) return '올바른 이메일 형식이 아닙니다';
    return null;
  }

  static String? password(String? value) {
    if (value == null || value.isEmpty) return '비밀번호를 입력해주세요';
    if (value.length < 6) return '비밀번호는 6자 이상이어야 합니다';
    return null;
  }

  static String? name(String? value) {
    if (value == null || value.isEmpty) return '이름을 입력해주세요';
    if (value.length < 2) return '이름은 2자 이상이어야 합니다';
    return null;
  }

  static String? phone(String? value) {
    if (value == null || value.isEmpty) return null;
    final phoneRegex = RegExp(r'^01[0-9]-?[0-9]{3,4}-?[0-9]{4}$');
    if (!phoneRegex.hasMatch(value)) return '올바른 전화번호 형식이 아닙니다';
    return null;
  }

  static String? required(String? value, [String fieldName = '필드']) {
    if (value == null || value.isEmpty) return '$fieldName를 입력해주세요';
    return null;
  }

  static String? rating(int? value) {
    if (value == null || value < 1 || value > 5) return '1~5 사이의 별점을 선택해주세요';
    return null;
  }
}
