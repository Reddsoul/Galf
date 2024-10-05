import SwiftUI

struct MainView: View {
    @State private var name: String = UserDefaults.standard.string(forKey: "userName") ?? "ENTER YOUR NAME"
    @State private var handicap: Double = UserDefaults.standard.double(forKey: "Handicap")
    @State private var recentRounds: [RoundModel] = []
    @State private var courses: [CourseModel] = []

    init() {
        loadSavedData()
    }

    var body: some View {
        NavigationView {
            VStack {
                TextField("Enter your name", text: $name)
                    .padding()
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .onChange(of: name) { newName in
                        UserDefaults.standard.set(newName, forKey: "userName")
                    }

                Text("Handicap: \(handicap, specifier: "%.1f")")
                    .font(.title)
                    .padding()
                    .onChange(of: handicap) { newHandicap in
                        UserDefaults.standard.set(newHandicap, forKey: "Handicap")
                    }

                List {
                    ForEach(recentRounds.prefix(5), id: \.date) { round in
                        NavigationLink(destination: RoundBreakdownView(round: round, courses: courses, par: totalParForRound(round))) {
                            VStack(alignment: .leading) {
                                Text(round.courseName)
                                HStack {
                                    Text("Par: \(totalParForRound(round))")
                                    Text("Score: \(round.totalToT, specifier: "%.0f")")
                                }
                                Text(round.isCompleted ? "Status: Completed" : "Status: Unfinished")
                                    .font(.caption)
                                    .foregroundColor(round.isCompleted ? .green : .red)
                            }
                        }
                    }
                    .onDelete(perform: deleteRound)
                }

                HStack {
                    NavigationLink(destination: NewRoundView(courses: courses, recentRounds: $recentRounds, handicap: $handicap)) {
                        Text("New Round")
                    }
                    .padding()

                    NavigationLink(destination: RecentRoundsView(recentRounds: $recentRounds, courses: courses, totalParForRound: totalParForRound)) {
                        Text("Recent Rounds")
                    }
                    .padding()

                    NavigationLink(destination: CourseManagementView(courses: $courses)) {
                        Text("Manage Courses")
                    }
                    .padding()
                }
            }
            .navigationTitle("Golf Scorecard")
        }
        .onAppear(perform: loadSavedData)  // Ensure data is loaded when view appears
    }

    private func totalParForRound(_ round: RoundModel) -> Int {
        return courses.filter { round.courseName.contains($0.courseName) }
                      .flatMap { $0.nine }
                      .reduce(0, +)
    }

    private func deleteRound(at offsets: IndexSet) {
        recentRounds.remove(atOffsets: offsets)
        saveRecentRounds()
    }

    private func loadSavedData() {
        if let savedRecentRounds = UserDefaults.standard.data(forKey: "recentRounds"),
           let decodedRecentRounds = try? JSONDecoder().decode([RoundModel].self, from: savedRecentRounds) {
            recentRounds = decodedRecentRounds
        } else {
            print("No recent rounds data found")  // Debug statement
        }

        if let savedCourses = UserDefaults.standard.data(forKey: "courses"),
           let decodedCourses = try? JSONDecoder().decode([CourseModel].self, from: savedCourses) {
            courses = decodedCourses
        } else {
            print("No courses data found")  // Debug statement
        }
    }

    private func saveRecentRounds() {
        if let encodedRounds = try? JSONEncoder().encode(recentRounds) {
            UserDefaults.standard.set(encodedRounds, forKey: "recentRounds")
        } else {
            print("Failed to encode recent rounds")  // Debug statement
        }
    }

    private func saveCourses() {
        if let encodedCourses = try? JSONEncoder().encode(courses) {
            UserDefaults.standard.set(encodedCourses, forKey: "courses")
        } else {
            print("Failed to encode courses")  // Debug statement
        }
    }
}
