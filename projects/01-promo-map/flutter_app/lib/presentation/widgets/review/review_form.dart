import 'package:flutter/material.dart';
import 'package:flutter_rating_bar/flutter_rating_bar.dart';
import '../../../app/constants.dart';
import '../common/primary_button.dart';

class ReviewForm extends StatefulWidget {
  final void Function(int rating, String content) onSubmit;
  final bool isLoading;

  const ReviewForm({super.key, required this.onSubmit, this.isLoading = false});

  @override
  State<ReviewForm> createState() => _ReviewFormState();
}

class _ReviewFormState extends State<ReviewForm> {
  int _rating = 0;
  final _contentController = TextEditingController();

  @override
  void dispose() {
    _contentController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '별점을 선택해주세요',
          style: TextStyle(fontWeight: FontWeight.w600, fontSize: 16),
        ),
        const SizedBox(height: 8),
        RatingBar.builder(
          initialRating: 0,
          minRating: 1,
          allowHalfRating: false,
          itemCount: 5,
          itemSize: 36,
          unratedColor: AppColors.divider,
          itemBuilder: (context, _) => const Icon(Icons.star, color: AppColors.star),
          onRatingUpdate: (rating) => _rating = rating.round(),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _contentController,
          maxLines: 3,
          decoration: const InputDecoration(
            hintText: '리뷰를 작성해주세요 (선택사항)',
          ),
        ),
        const SizedBox(height: 16),
        PrimaryButton(
          text: '리뷰 등록',
          isLoading: widget.isLoading,
          onPressed: _rating > 0
              ? () => widget.onSubmit(_rating, _contentController.text)
              : null,
        ),
      ],
    );
  }
}
