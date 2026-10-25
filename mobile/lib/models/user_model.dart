class UserModel {
  final int? id;
  final String name;
  final double weight;
  final double height;
  final String goal;

  UserModel({
    this.id,
    required this.name,
    required this.weight,
    required this.height,
    required this.goal,
  });

  UserModel copyWith({
    int? id,
    String? name,
    double? weight,
    double? height,
    String? goal,
  }) {
    return UserModel(
      id: id ?? this.id,
      name: name ?? this.name,
      weight: weight ?? this.weight,
      height: height ?? this.height,
      goal: goal ?? this.goal,
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'name': name,
      'weight': weight,
      'height': height,
      'goal': goal,
    };
  }

  factory UserModel.fromMap(Map<String, dynamic> map) {
    return UserModel(
      id: map['id'] as int?,
      name: map['name'] as String,
      weight: (map['weight'] as num).toDouble(),
      height: (map['height'] as num).toDouble(),
      goal: map['goal'] as String,
    );
  }
}
