import Foundation

class RoundModel: CourseModel {
    var date: Int
    var totalToT: Double
    var playedNine: [[Int]]
    var scoreDifferential: Double
    var isCompleted: Bool = false

    enum CodingKeys: String, CodingKey {
        case date, totalToT, playedNine, scoreDifferential, isCompleted
    }

    required init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        date = try container.decode(Int.self, forKey: .date)
        totalToT = try container.decode(Double.self, forKey: .totalToT)
        playedNine = try container.decode([[Int]].self, forKey: .playedNine)
        scoreDifferential = try container.decode(Double.self, forKey: .scoreDifferential)
        isCompleted = try container.decode(Bool.self, forKey: .isCompleted)
        try super.init(from: decoder)
    }

    override func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(date, forKey: .date)
        try container.encode(totalToT, forKey: .totalToT)
        try container.encode(playedNine, forKey: .playedNine)
        try container.encode(scoreDifferential, forKey: .scoreDifferential)
        try container.encode(isCompleted, forKey: .isCompleted)
        try super.encode(to: encoder)
    }

    override init() {
        date = 0
        totalToT = 0.0
        playedNine = [[Int]](repeating: [Int](repeating: 0, count: 9), count: 1)
        scoreDifferential = 0.0
        super.init()
    }
}
