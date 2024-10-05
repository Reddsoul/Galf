import SwiftUI

struct CourseManagementView: View {
    @Binding var courses: [CourseModel]

    var body: some View {
        VStack {
            NavigationLink(destination: AddCourseView(courses: $courses)) {
                Text("Add New Course")
                    .padding()
                    .background(Color.green)
                    .foregroundColor(.white)
                    .cornerRadius(8)
            }
            .padding()

            List {
                ForEach(courses, id: \.id) { course in
                    NavigationLink(destination: AddCourseView(courses: $courses, course: course)) {
                        Text(course.courseName)
                    }
                }
                .onDelete(perform: deleteCourse)
            }
        }
        .navigationTitle("Manage Courses")
    }

    private func deleteCourse(at offsets: IndexSet) {
        courses.remove(atOffsets: offsets)
        saveCourses()
    }

    private func saveCourses() {
        if let encodedCourses = try? JSONEncoder().encode(courses) {
            UserDefaults.standard.set(encodedCourses, forKey: "courses")
        } else {
            print("Failed to encode courses")  // Debug statement
        }
    }
}
