import Foundation

class HandicapModel: ObservableObject {
    @Published var handicapIndex = 0.0
    @Published var courseHandicap = 0.0
    @Published var avgScoreDifferential = 0.0
    
    func calculateAvgScoreDifferential(roundModels: [RoundModel]) {
        let completedRounds = roundModels.filter { $0.isCompleted }
        let sortedRounds = completedRounds.sorted { $0.scoreDifferential < $1.scoreDifferential }
        let lowest20Rounds = sortedRounds.prefix(20)
        let sumOfDifferentials = lowest20Rounds.reduce(0) { $0 + $1.scoreDifferential }
        
        if !lowest20Rounds.isEmpty {
            avgScoreDifferential = sumOfDifferentials / Double(lowest20Rounds.count)
        } else {
            avgScoreDifferential = 0.0
        }
    }
    
    func calculateHandicapIndex() {
        handicapIndex = avgScoreDifferential * 0.96
        handicapIndex = Double(String(format: "%.1f", handicapIndex)) ?? 0.0
    }
    
    func calculateCourseHandicap(slopeRating: Double, courseRating: Double, par: Double) {
        courseHandicap = (handicapIndex * (slopeRating / 113.0)) + (courseRating - par)
        courseHandicap = Double(String(format: "%.0f", courseHandicap)) ?? 0.0
    }
}
