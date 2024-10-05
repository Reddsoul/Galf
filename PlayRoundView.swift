import SwiftUI

struct PlayRoundView: View {
    @State private var currentHole: Int = 1
    @State private var strokes: [[Int]]
    @State private var isRoundFinished = false
    var courses: [CourseModel]
    var teeColors: [UUID: String]
    @Binding var recentRounds: [RoundModel]
    @Binding var handicap: Double
    @State private var currentCourseIndex = 0

    init(courses: [CourseModel], teeColors: [UUID: String], recentRounds: Binding<[RoundModel]>, handicap: Binding<Double>) {
        self.courses = courses
        self.teeColors = teeColors
        self._strokes = State(initialValue: courses.map { Array(repeating: 0, count: $0.nine.count) })
        self._recentRounds = recentRounds
        self._handicap = handicap
    }

    var body: some View {
        VStack {
            Text("Course: \(courses[currentCourseIndex].courseName)")
                .font(.headline)
                .padding(.top)
            Text("Tee: \(teeColors[courses[currentCourseIndex].id] ?? "")")
                .font(.subheadline)
                .padding(.bottom)

            Text("Hole \(currentHole)")
                .font(.largeTitle)
            
            // Hole navigation and stroke counter
            HStack {
                Button(action: {
                    if strokes[currentCourseIndex][currentHole - 1] > 0 {
                        strokes[currentCourseIndex][currentHole - 1] -= 1
                    }
                }) {
                    Image(systemName: "minus.circle")
                        .font(.largeTitle)
                }
                Text("\(strokes[currentCourseIndex][currentHole - 1])")
                    .font(.largeTitle)
                Button(action: {
                    strokes[currentCourseIndex][currentHole - 1] += 1
                }) {
                    Image(systemName: "plus.circle")
                        .font(.largeTitle)
                }
            }
            .padding()

            // Navigation buttons
            HStack {
                Button(action: {
                    if currentHole > 1 {
                        currentHole -= 1
                    } else if currentCourseIndex > 0 {
                        currentCourseIndex -= 1
                        currentHole = courses[currentCourseIndex].nine.count
                    }
                }) {
                    Text("Previous Hole")
                        .padding()
                        .background(Color.green)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }
                .disabled(currentHole == 1 && currentCourseIndex == 0)

                Button(action: {
                    endRound()
                }) {
                    Text("End Round")
                        .padding()
                        .background(Color.red)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }
                .padding()

                Button(action: {
                    if currentHole < strokes[currentCourseIndex].count {
                        currentHole += 1
                    } else if currentCourseIndex < courses.count - 1 {
                        currentCourseIndex += 1
                        currentHole = 1
                    } else {
                        finishRound()
                        isRoundFinished = true
                    }
                }) {
                    Text("Next Hole")
                        .padding()
                        .background(Color.green)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }
            }
            .padding()

            NavigationLink(
                destination: RoundBreakdownView(round: recentRounds.last ?? RoundModel(), courses: courses, par: totalParForRound()),
                isActive: $isRoundFinished,
                label: {
                    EmptyView()
                }
            )
        }
        .navigationTitle("Play Round")
    }

    private func finishRound() {
        let newRound = RoundModel()
        newRound.courseName = courses.map { $0.courseName }.joined(separator: ", ")
        newRound.playedNine = strokes
        newRound.totalToT = Double(strokes.flatMap { $0 }.reduce(0, +))
        newRound.scoreDifferential = ((newRound.totalToT - (courses.first?.courseRating.first ?? 72.0)) * 113) / (courses.first?.slopeRating.first ?? 113.0)
        newRound.scoreDifferential = (newRound.scoreDifferential * 10).rounded() / 10
        newRound.date = Int(Date().timeIntervalSince1970)
        newRound.isCompleted = true

        recentRounds.append(newRound)
        calculateHandicap()

        do {
            let encodedRounds = try JSONEncoder().encode(recentRounds)
            UserDefaults.standard.set(encodedRounds, forKey: "recentRounds")
        } catch {
            print("Failed to encode recent rounds: \(error)")
        }
    }

    private func calculateHandicap() {
        let handicapModel = HandicapModel()
        handicapModel.calculateAvgScoreDifferential(roundModels: recentRounds)
        handicapModel.calculateHandicapIndex()
        handicap = handicapModel.handicapIndex
    }

    private func totalParForRound() -> Int {
        return courses.flatMap { $0.nine }.reduce(0, +)
    }

    private func endRound() {
        for courseIndex in currentCourseIndex..<courses.count {
            for holeIndex in (courseIndex == currentCourseIndex ? currentHole - 1 : 0)..<strokes[courseIndex].count {
                strokes[courseIndex][holeIndex] = 0
            }
        }
        let unfinishedRound = RoundModel()
        unfinishedRound.courseName = courses.map { $0.courseName }.joined(separator: ", ")
        unfinishedRound.playedNine = strokes
        unfinishedRound.totalToT = Double(strokes.flatMap { $0 }.reduce(0, +))
        unfinishedRound.scoreDifferential = ((unfinishedRound.totalToT - (courses.first?.courseRating.first ?? 72.0)) * 113) / (courses.first?.slopeRating.first ?? 113.0)
        unfinishedRound.scoreDifferential = (unfinishedRound.scoreDifferential * 10).rounded() / 10
        unfinishedRound.date = Int(Date().timeIntervalSince1970)
        unfinishedRound.isCompleted = false

        recentRounds.append(unfinishedRound)

        do {
            let encodedRounds = try JSONEncoder().encode(recentRounds)
            UserDefaults.standard.set(encodedRounds, forKey: "recentRounds")
        } catch {
            print("Failed to encode recent rounds: \(error)")
        }
        isRoundFinished = true
    }
}
