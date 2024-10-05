import SwiftUI

struct AddCourseView: View {
    @Binding var courses: [CourseModel]
    @State private var courseName: String = ""
    @State private var pars: [Int] = Array(repeating: 4, count: 9)
    @State private var teeColors: [String] = [""]
    @State private var courseRatings: [Double] = [0.0]
    @State private var slopeIndexes: [Double] = [0.0]

    var course: CourseModel?

    private var decimalFormatter: NumberFormatter {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.minimumFractionDigits = 1
        formatter.maximumFractionDigits = 2
        return formatter
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                TextField("Course Name", text: $courseName)
                    .padding()
                    .textFieldStyle(RoundedBorderTextFieldStyle())

                ForEach(0..<9, id: \.self) { index in
                    HStack {
                        Text("Hole \(index + 1)")
                        Spacer()
                        TextField("Par", value: $pars[index], formatter: NumberFormatter())
                            .keyboardType(.numberPad)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                            .frame(width: 50)
                    }
                    .padding(.horizontal)
                }

                Text("Tee Information")
                    .font(.headline)

                ForEach(0..<teeColors.count, id: \.self) { index in
                    HStack {
                        VStack {
                            Text("Tee\nColor")
                            TextField("Tee Color", text: $teeColors[index])
                                .textFieldStyle(RoundedBorderTextFieldStyle())
                        }
                        VStack {
                            Text("Course\nRating")
                            TextField("Course Rating", value: $courseRatings[index], formatter: decimalFormatter)
                                .keyboardType(.decimalPad)
                                .textFieldStyle(RoundedBorderTextFieldStyle())
                        }
                        VStack {
                            Text("Slope\nIndex")
                            TextField("Slope Index", value: $slopeIndexes[index], formatter: decimalFormatter)
                                .keyboardType(.decimalPad)
                                .textFieldStyle(RoundedBorderTextFieldStyle())
                        }
                    }
                    .padding(.horizontal)
                }

                Button(action: {
                    teeColors.append("")
                    courseRatings.append(0.0)
                    slopeIndexes.append(0.0)
                }) {
                    Text("Add Tee")
                        .padding()
                        .background(Color.green)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }

                Button(action: saveCourse) {
                    Text(course != nil ? "Update Course" : "Save Course")
                        .padding()
                        .background(Color.blue)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }
            }
            .padding()
        }
        .navigationTitle(course != nil ? "Edit Course" : "Add Course")
        .onAppear {
            if let course = course {
                courseName = course.courseName
                pars = course.nine
                teeColors = course.teeColors
                courseRatings = course.courseRating
                slopeIndexes = course.slopeRating
            }
        }
    }

    private func saveCourse() {
        if let course = course {
            if let index = courses.firstIndex(where: { $0.id == course.id }) {
                courses[index].courseName = courseName
                courses[index].nine = pars
                courses[index].teeColors = teeColors
                courses[index].courseRating = courseRatings
                courses[index].slopeRating = slopeIndexes
            }
        } else {
            let newCourse = CourseModel()
            newCourse.courseName = courseName
            newCourse.teeColors = teeColors
            newCourse.courseRating = courseRatings
            newCourse.slopeRating = slopeIndexes
            newCourse.par = Double(pars.reduce(0, +))
            newCourse.nine = pars
            courses.append(newCourse)
        }

        if let encodedCourses = try? JSONEncoder().encode(courses) {
            UserDefaults.standard.set(encodedCourses, forKey: "courses")
        } else {
            print("Failed to encode courses")  // Debug statement
        }
        clearForm()
    }

    private func clearForm() {
        courseName = ""
        pars = Array(repeating: 4, count: 9)
        teeColors = [""]
        courseRatings = [0.0]
        slopeIndexes = [0.0]
    }
}
