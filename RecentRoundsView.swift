import SwiftUI

struct RecentRoundsView: View {
    @Binding var recentRounds: [RoundModel]
    var courses: [CourseModel]
    var totalParForRound: (RoundModel) -> Int

    var body: some View {
        VStack {
            List {
                ForEach(recentRounds, id: \.date) { round in
                    NavigationLink(destination: RoundBreakdownView(round: round, courses: courses, par: totalParForRound(round))) {
                        VStack(alignment: .leading) {
                            Text(round.courseName)
                            HStack {
                                Text("Par: \(totalParForRound(round))")
                                Text("Score: \(round.totalToT, specifier: "%.0f")")
                                Text(round.isCompleted ? "Status: Completed" : "Status: Unfinished")
                                    .font(.caption)
                                    .foregroundColor(round.isCompleted ? .green : .red)
                            }
                        }
                    }
                }
                .onDelete(perform: deleteRound)
            }
        }
        .navigationTitle("Recent Rounds")
        .onAppear(perform: loadRecentRounds)
    }

    private func deleteRound(at offsets: IndexSet) {
        recentRounds.remove(atOffsets: offsets)
        saveRecentRounds()
    }

    private func saveRecentRounds() {
        if let encodedRounds = try? JSONEncoder().encode(recentRounds) {
            UserDefaults.standard.set(encodedRounds, forKey: "recentRounds")
        } else {
            print("Failed to encode recent rounds") // Debug statement
        }
    }

    private func loadRecentRounds() {
        if let savedRoundsData = UserDefaults.standard.data(forKey: "recentRounds"),
           let savedRounds = try? JSONDecoder().decode([RoundModel].self, from: savedRoundsData) {
            recentRounds = savedRounds
        } else {
            print("Failed to load recent rounds") // Debug statement
        }
    }
}
