import SwiftUI

struct RoundBreakdownView: View {
    var round: RoundModel
    var courses: [CourseModel]
    var par: Int

    var body: some View {
        ScrollView {
            VStack(alignment: .leading) {
                Text("Round Breakdown")
                    .font(.largeTitle)
                    .padding()

                ForEach(Array(round.playedNine.enumerated()), id: \.offset) { index, nineHoles in
                    let course = courses[index]
                    let courseTotalPar = course.nine.reduce(0, +)
                    let courseTotalStrokes = nineHoles.reduce(0, +)
                    RoundSectionView(course: course, nineHoles: nineHoles, totalPar: courseTotalPar, totalStrokes: courseTotalStrokes)
                }

                HStack {
                    Text("Total Par: \(par)")
                        .font(.headline)
                        .padding()
                    Text("Total Strokes: \(round.totalToT, specifier: "%.0f")")
                        .font(.headline)
                        .padding()
                }

                Text("Score Differential: \(round.scoreDifferential, specifier: "%.1f")")
                    .padding()

                Text("Date: \(formattedDate(from: round.date))")
                    .padding()
            }
        }
        .navigationTitle("Round Breakdown")
    }

    private func formattedDate(from timestamp: Int) -> String {
        let date = Date(timeIntervalSince1970: TimeInterval(timestamp))
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .none
        return formatter.string(from: date)
    }
}

struct RoundSectionView: View {
    var course: CourseModel
    var nineHoles: [Int]
    var totalPar: Int
    var totalStrokes: Int

    var body: some View {
        VStack(alignment: .leading) {
            Text("Course: \(course.courseName)")
                .font(.headline)
                .padding(.top)
                .padding(.bottom)

            ForEach(Array(nineHoles.enumerated()), id: \.offset) { holeIndex, strokes in
                HoleView(holeIndex: holeIndex, par: course.nine[holeIndex], strokes: strokes)
            }

            HStack {
                Text("Total Par: \(totalPar)")
                    .font(.subheadline)
                    .padding()
                Text("Total Strokes: \(totalStrokes)")
                    .font(.subheadline)
                    .padding()
            }
        }
        .padding()
        .background(Color(UIColor.secondarySystemBackground))
        .cornerRadius(10)
        .padding(.horizontal)
        .padding(.vertical, 4)
    }
}

struct HoleView: View {
    var holeIndex: Int
    var par: Int
    var strokes: Int

    var body: some View {
        HStack {
            Text("Hole \(holeIndex + 1):")
            Spacer()
            Text("Par: \(par)")
            Spacer()
            Text("\(strokes) strokes")
        }
        .padding(.horizontal)
        .padding(.vertical, 4)
    }
}
