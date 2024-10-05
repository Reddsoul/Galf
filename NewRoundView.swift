import SwiftUI

struct NewRoundView: View {
    @State private var selectedCourses: [CourseModel] = []
    @State private var selectedTeeColors: [UUID: String] = [:]
    @State private var courses: [CourseModel]
    @Binding private var recentRounds: [RoundModel]
    @Binding private var handicap: Double

    public init(courses: [CourseModel], recentRounds: Binding<[RoundModel]>, handicap: Binding<Double>) {
        self._courses = State(initialValue: courses)
        self._recentRounds = recentRounds
        self._handicap = handicap
    }

    var body: some View {
        VStack {
            List {
                ForEach(courses, id: \.id) { course in
                    Toggle(isOn: Binding(
                        get: { self.selectedCourses.contains(course) },
                        set: { isSelected in
                            if isSelected {
                                self.selectedCourses.append(course)
                                self.selectedTeeColors[course.id] = course.teeColors.first ?? ""
                            } else {
                                self.selectedCourses.removeAll { $0 == course }
                                self.selectedTeeColors.removeValue(forKey: course.id)
                            }
                        }
                    )) {
                        Text(course.courseName)
                    }
                }
            }

            ForEach(selectedCourses, id: \.id) { course in
                Picker("Tee Color for \(course.courseName)", selection: Binding(
                    get: { self.selectedTeeColors[course.id] ?? course.teeColors.first ?? "" },
                    set: { newValue in self.selectedTeeColors[course.id] = newValue }
                )) {
                    ForEach(course.teeColors, id: \.self) { color in
                        Text(color).tag(color)
                    }
                }
                .pickerStyle(MenuPickerStyle())
            }

            if !selectedCourses.isEmpty {
                NavigationLink(destination: PlayRoundView(courses: selectedCourses, teeColors: selectedTeeColors, recentRounds: $recentRounds, handicap: $handicap)) {
                    Text("Start Round")
                        .padding()
                        .background(Color.blue)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }
                .padding()
            }
        }
        .navigationTitle("New Round")
        .padding()
    }
}
