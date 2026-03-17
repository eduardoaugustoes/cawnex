import SwiftUI

struct InputFieldView: View {
    let field: InputField
    @Binding var value: String

    var body: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.xs) {
            // Label
            HStack(spacing: 4) {
                Text(field.label)
                    .font(CawnexTypography.captionBold)
                    .foregroundColor(CawnexColors.cardForeground)
                if field.required {
                    Text("*")
                        .font(CawnexTypography.captionBold)
                        .foregroundColor(.red)
                }
            }

            // Description
            if !field.description.isEmpty {
                Text(field.description)
                    .font(CawnexTypography.tiny)
                    .foregroundColor(CawnexColors.mutedForeground)
            }

            // Input widget by type
            inputWidget
        }
    }

    // MARK: - Input Widgets

    @ViewBuilder
    private var inputWidget: some View {
        switch field.type {
        case .string, .url, .email:
            textField
        case .text:
            textArea
        case .secret:
            secretField
        case .file:
            filePickerPlaceholder
        case .color:
            colorField
        case .enum:
            enumPicker
        case .boolean:
            toggleField
        case .number:
            numberField
        }
    }

    private var textField: some View {
        TextField(field.placeholder, text: $value)
            .font(CawnexTypography.body)
            .foregroundColor(CawnexColors.cardForeground)
            .padding(CawnexSpacing.sm)
            .background(CawnexColors.cardElevated)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
            .autocorrectionDisabled()
            .textInputAutocapitalization(.never)
    }

    private var textArea: some View {
        TextEditor(text: $value)
            .font(CawnexTypography.body)
            .foregroundColor(CawnexColors.cardForeground)
            .scrollContentBackground(.hidden)
            .frame(minHeight: 100)
            .padding(CawnexSpacing.sm)
            .background(CawnexColors.cardElevated)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
    }

    private var secretField: some View {
        SecureField(field.placeholder, text: $value)
            .font(CawnexTypography.body)
            .foregroundColor(CawnexColors.cardForeground)
            .padding(CawnexSpacing.sm)
            .background(CawnexColors.cardElevated)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
    }

    private var filePickerPlaceholder: some View {
        Button {
            // File picker integration — handled by parent via upload URL flow
        } label: {
            HStack {
                Image(systemName: "arrow.up.doc")
                    .foregroundColor(CawnexColors.primary)
                Text(value.isEmpty ? "Choose file..." : value)
                    .font(CawnexTypography.body)
                    .foregroundColor(value.isEmpty ? CawnexColors.mutedForeground : CawnexColors.cardForeground)
                Spacer()
            }
            .padding(CawnexSpacing.sm)
            .background(CawnexColors.cardElevated)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
        }
        .buttonStyle(.plain)
    }

    private var colorField: some View {
        HStack {
            TextField("#RRGGBB", text: $value)
                .font(CawnexTypography.mono)
                .foregroundColor(CawnexColors.cardForeground)
                .padding(CawnexSpacing.sm)
                .background(CawnexColors.cardElevated)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))

            if value.count == 7, value.hasPrefix("#") {
                RoundedRectangle(cornerRadius: CawnexRadius.sm)
                    .fill(Color(hex: value))
                    .frame(width: 36, height: 36)
            }
        }
    }

    private var enumPicker: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.xs) {
            ForEach(field.options, id: \.value) { option in
                Button {
                    value = option.value
                } label: {
                    HStack {
                        Image(systemName: value == option.value ? "checkmark.circle.fill" : "circle")
                            .foregroundColor(value == option.value ? CawnexColors.primary : CawnexColors.mutedForeground)
                        Text(option.label)
                            .font(CawnexTypography.body)
                            .foregroundColor(CawnexColors.cardForeground)
                        Spacer()
                    }
                    .padding(CawnexSpacing.sm)
                    .background(value == option.value ? CawnexColors.primary.opacity(0.1) : CawnexColors.cardElevated)
                    .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
                }
                .buttonStyle(.plain)
            }
        }
    }

    private var toggleField: some View {
        Toggle(isOn: Binding(
            get: { value == "true" },
            set: { value = $0 ? "true" : "false" }
        )) {
            Text(field.label)
                .font(CawnexTypography.body)
                .foregroundColor(CawnexColors.cardForeground)
        }
        .tint(CawnexColors.primary)
    }

    private var numberField: some View {
        TextField(field.placeholder, text: $value)
            .font(CawnexTypography.body)
            .foregroundColor(CawnexColors.cardForeground)
            .keyboardType(.decimalPad)
            .padding(CawnexSpacing.sm)
            .background(CawnexColors.cardElevated)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.sm))
    }
}

// Color hex extension for preview
private extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let r = Double((int >> 16) & 0xFF) / 255.0
        let g = Double((int >> 8) & 0xFF) / 255.0
        let b = Double(int & 0xFF) / 255.0
        self.init(red: r, green: g, blue: b)
    }
}

#Preview {
    VStack(spacing: 16) {
        InputFieldView(
            field: InputField(
                id: "phone",
                type: .string,
                label: "Phone number",
                placeholder: "+55 11 99999-9999",
                description: "E.164 format",
                required: true,
                pattern: nil,
                patternHint: nil,
                minLength: nil,
                maxLength: nil,
                accept: [],
                maxSizeMB: nil,
                options: [],
                min: nil,
                max: nil
            ),
            value: .constant("")
        )
    }
    .padding()
    .background(CawnexColors.background)
    .preferredColorScheme(.dark)
}
