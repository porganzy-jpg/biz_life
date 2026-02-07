class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final dynamic data;

  ApiException({required this.message, this.statusCode, this.data});

  @override
  String toString() => 'ApiException($statusCode): $message';
}

class UnauthorizedException extends ApiException {
  UnauthorizedException({String message = '인증이 필요합니다'})
      : super(message: message, statusCode: 401);
}

class ForbiddenException extends ApiException {
  ForbiddenException({String message = '접근 권한이 없습니다'})
      : super(message: message, statusCode: 403);
}

class NotFoundException extends ApiException {
  NotFoundException({String message = '요청한 리소스를 찾을 수 없습니다'})
      : super(message: message, statusCode: 404);
}

class ConflictException extends ApiException {
  ConflictException({String message = '이미 존재하는 데이터입니다'})
      : super(message: message, statusCode: 409);
}

class ServerException extends ApiException {
  ServerException({String message = '서버 오류가 발생했습니다'})
      : super(message: message, statusCode: 500);
}

class NetworkException extends ApiException {
  NetworkException({String message = '네트워크 연결을 확인해주세요'})
      : super(message: message, statusCode: null);
}
