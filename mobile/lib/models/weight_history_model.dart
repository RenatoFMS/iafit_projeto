class WeightHistoryModel {
  final int? id;
  final double weight;
  final String date;

  WeightHistoryModel({this.id, required this.weight, required this.date});

  Map<String, dynamic> toMap() {
    return {'id': id, 'weight': weight, 'date': date};
  }

  factory WeightHistoryModel.fromMap(Map<String, dynamic> map) {
    return WeightHistoryModel(
      id: map['id'] as int?,
      weight: (map['weight'] as num).toDouble(),
      date: map['date'] as String,
    );
  }
}
