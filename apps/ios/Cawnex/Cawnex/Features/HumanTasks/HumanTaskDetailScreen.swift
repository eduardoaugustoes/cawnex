import SwiftUI

struct HumanTaskDetailScreen: View {
    @State var viewModel: HumanTaskViewModel
    let humanTaskId: String
    var onBack: () -> Void = {}

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: CawnexSpacing.xl) {
                navRow

                switch viewModel.detailState {
                case .idle, .loading:
                    loadingView
                case .loaded(let detail):
                    detailContent(detail)
                case .error(let message):
                    errorView(message)
                }
            }
            .padding(.horizontal, CawnexSpacing.lg)
        }
        .background(CawnexColors.background)
        .navigationBarHidden(true)
        .task { await viewModel.loadDetail(humanTaskId: humanTaskId) }
    }

    // MARK: - Navigation

    private var navRow: some View {
        HStack {
            Button(action: onBack) {
                Image(systemName: "chevron.left")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundColor(CawnexColors.cardForeground)
            }
            Text("Task Detail")
                .font(CawnexTypography.heading2)
                .foregroundColor(CawnexColors.cardForeground)
            Spacer()
        }
        .padding(.top, CawnexSpacing.md)
    }

    // MARK: - Detail Content

    private func detailContent(_ detail: HumanTaskDetail) -> some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.xl) {
            // Ask
            Text(detail.ask)
                .font(CawnexTypography.heading3)
                .foregroundColor(CawnexColors.cardForeground)

            // Instructions
            Text(detail.instructions)
                .font(CawnexTypography.body)
                .foregroundColor(CawnexColors.mutedForeground)

            // What this unblocks
            if !detail.blocks.isEmpty {
                VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
                    Text("Unblocks")
                        .font(CawnexTypography.captionBold)
                        .foregroundColor(CawnexColors.mutedForeground)
                    ForEach(detail.blocks, id: \.self) { block in
                        HStack(spacing: CawnexSpacing.sm) {
                            Image(systemName: "link")
                                .font(.system(size: 12))
                                .foregroundColor(CawnexColors.primary)
                            Text(block)
                                .font(CawnexTypography.caption)
                                .foregroundColor(CawnexColors.mutedForeground)
                        }
                    }
                }
            }

            // Input fields
            if detail.status.isActionable {
                Divider().background(CawnexColors.border)

                ForEach(detail.inputSchema) { field in
                    InputFieldView(
                        field: field,
                        value: Binding(
                            get: { viewModel.fieldValues[field.id] ?? "" },
                            set: { viewModel.fieldValues[field.id] = $0 }
                        )
                    )
                }

                // Steer text area
                steerSection

                // Submit
                if let error = viewModel.submitError {
                    Text(error)
                        .font(CawnexTypography.caption)
                        .foregroundColor(.red)
                }

                submitButton
            }
        }
    }

    // MARK: - Steer

    private var steerSection: some View {
        VStack(alignment: .leading, spacing: CawnexSpacing.sm) {
            Divider().background(CawnexColors.border)

            Text("Guidance for the AI (optional)")
                .font(CawnexTypography.captionBold)
                .foregroundColor(CawnexColors.mutedForeground)

            Text("You can skip the fields above if your guidance replaces the original request")
                .font(CawnexTypography.tiny)
                .foregroundColor(CawnexColors.mutedForeground)

            TextEditor(text: $viewModel.steerText)
                .font(CawnexTypography.body)
                .foregroundColor(CawnexColors.cardForeground)
                .scrollContentBackground(.hidden)
                .frame(minHeight: 80)
                .padding(CawnexSpacing.sm)
                .background(CawnexColors.cardElevated)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
    }

    // MARK: - Submit

    private var submitButton: some View {
        Button {
            Task { await viewModel.submit(humanTaskId: humanTaskId) }
        } label: {
            HStack {
                if viewModel.isSubmitting {
                    ProgressView()
                        .tint(.white)
                } else {
                    Text("Submit")
                        .font(CawnexTypography.bodyBold)
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, CawnexSpacing.md)
            .background(CawnexColors.primary)
            .foregroundColor(.white)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
        .disabled(viewModel.isSubmitting)
        .padding(.bottom, CawnexSpacing.xxl)
    }

    // MARK: - States

    private var loadingView: some View {
        VStack(spacing: CawnexSpacing.lg) {
            ProgressView()
                .tint(CawnexColors.primary)
            Text("Loading task...")
                .font(CawnexTypography.body)
                .foregroundColor(CawnexColors.mutedForeground)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 100)
    }

    private func errorView(_ message: String) -> some View {
        VStack(spacing: CawnexSpacing.md) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 32))
                .foregroundColor(.red)
            Text(message)
                .font(CawnexTypography.body)
                .foregroundColor(CawnexColors.mutedForeground)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 100)
    }
}

#Preview {
    HumanTaskDetailScreen(
        viewModel: HumanTaskViewModel(
            humanTaskService: InMemoryHumanTaskService(store: AppStore()),
            projectId: "proj-001"
        ),
        humanTaskId: "ht_esim"
    )
    .preferredColorScheme(.dark)
}
