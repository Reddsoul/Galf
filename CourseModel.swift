import Foundation

class CourseModel: Identifiable, ObservableObject, Hashable, Codable {
    static func == (lhs: CourseModel, rhs: CourseModel) -> Bool {
        return lhs.id == rhs.id
    }
    
    func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }
    
    var id = UUID()
    var courseName = ""
    var teeColors = [String]()
    var slopeRating = [Double]()
    var courseRating = [Double]()
    var par = 0.0
    var nine = [Int](repeating: 0, count: 9)
    
    enum CodingKeys: String, CodingKey {
        case id, courseName, teeColors, slopeRating, courseRating, par, nine
    }
    
    required init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(UUID.self, forKey: .id)
        courseName = try container.decode(String.self, forKey: .courseName)
        teeColors = try container.decode([String].self, forKey: .teeColors)
        slopeRating = try container.decode([Double].self, forKey: .slopeRating)
        courseRating = try container.decode([Double].self, forKey: .courseRating)
        par = try container.decode(Double.self, forKey: .par)
        nine = try container.decode([Int].self, forKey: .nine)
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(courseName, forKey: .courseName)
        try container.encode(teeColors, forKey: .teeColors)
        try container.encode(slopeRating, forKey: .slopeRating)
        try container.encode(courseRating, forKey: .courseRating)
        try container.encode(par, forKey: .par)
        try container.encode(nine, forKey: .nine)
    }
    
    init() {
        // Default initializer
    }
}
