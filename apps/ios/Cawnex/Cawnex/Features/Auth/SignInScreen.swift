import SwiftUI

struct SignInScreen: View {
    @State private var email = ""
    @State private var password = ""
    @State private var passwordVisible = false

    var onSignIn: () -> Void

    var body: some View {
        ZStack {
            CawnexColors.background
                .ignoresSafeArea()

            VStack(spacing: CawnexSpacing.xxxl) {
                logoSection
                formSection
                divider
                appleSignIn
                footer
            }
            .padding(.horizontal, 32)
        }
    }

    // MARK: - Logo

    private var logoSection: some View {
        VStack(spacing: CawnexSpacing.md) {
            Image("AppIconImage")
                .resizable()
                .aspectRatio(contentMode: .fit)
                .frame(width: 72, height: 72)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))

            Text("CAWNEX")
                .font(.custom("Inter", size: 28).weight(.bold))
                .tracking(4)
                .foregroundStyle(CawnexColors.cardForeground)

            Text("Coordinated Intelligence")
                .font(CawnexTypography.caption)
                .tracking(1)
                .foregroundStyle(CawnexColors.mutedForeground)
        }
    }

    // MARK: - Form

    private var formSection: some View {
        VStack(spacing: CawnexSpacing.lg) {
            emailField
            passwordField
            signInButton
        }
    }

    private var emailField: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Email")
                .font(.custom("Inter", size: 13).weight(.medium))
                .foregroundStyle(CawnexColors.mutedForeground)

            HStack(spacing: 10) {
                Image(systemName: "envelope")
                    .font(.system(size: 16))
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .frame(width: 18, height: 18)

                TextField("", text: $email, prompt: Text("your@email.com").foregroundStyle(Color(hex: 0x475569)))
                    .font(.custom("Inter", size: 15))
                    .foregroundStyle(CawnexColors.cardForeground)
                    .textContentType(.emailAddress)
                    .keyboardType(.emailAddress)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)
            }
            .padding(.horizontal, 16)
            .frame(height: 48)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(CawnexColors.border, lineWidth: 1)
            )
        }
    }

    private var passwordField: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Password")
                .font(.custom("Inter", size: 13).weight(.medium))
                .foregroundStyle(CawnexColors.mutedForeground)

            HStack(spacing: 10) {
                Image(systemName: "lock")
                    .font(.system(size: 16))
                    .foregroundStyle(CawnexColors.mutedForeground)
                    .frame(width: 18, height: 18)

                Group {
                    if passwordVisible {
                        TextField("", text: $password, prompt: Text("••••••••").foregroundStyle(Color(hex: 0x475569)))
                    } else {
                        SecureField("", text: $password, prompt: Text("••••••••").foregroundStyle(Color(hex: 0x475569)))
                    }
                }
                .font(.custom("Inter", size: 15))
                .foregroundStyle(CawnexColors.cardForeground)
                .textContentType(.password)

                Button {
                    passwordVisible.toggle()
                } label: {
                    Image(systemName: passwordVisible ? "eye" : "eye.slash")
                        .font(.system(size: 16))
                        .foregroundStyle(CawnexColors.mutedForeground)
                }
            }
            .padding(.horizontal, 16)
            .frame(height: 48)
            .background(CawnexColors.card)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: CawnexRadius.md)
                    .stroke(CawnexColors.border, lineWidth: 1)
            )
        }
    }

    private var signInButton: some View {
        Button(action: onSignIn) {
            Text("Sign In")
                .font(.custom("Inter", size: 16).weight(.semibold))
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 50)
                .background(CawnexColors.primaryLight)
                .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
    }

    // MARK: - Divider

    private var divider: some View {
        HStack(spacing: CawnexSpacing.lg) {
            Rectangle()
                .fill(CawnexColors.border)
                .frame(height: 1)
            Text("or")
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.mutedForeground)
            Rectangle()
                .fill(CawnexColors.border)
                .frame(height: 1)
        }
    }

    // MARK: - Apple Sign In

    private var appleSignIn: some View {
        Button {
            onSignIn()
        } label: {
            HStack(spacing: 10) {
                Image(systemName: "apple.logo")
                    .font(.system(size: 18))
                    .foregroundStyle(.black)
                Text("Continue with Apple")
                    .font(.custom("Inter", size: 16).weight(.semibold))
                    .foregroundStyle(.black)
            }
            .frame(maxWidth: .infinity)
            .frame(height: 50)
            .background(.white)
            .clipShape(RoundedRectangle(cornerRadius: CawnexRadius.md))
        }
    }

    // MARK: - Footer

    private var footer: some View {
        HStack(spacing: 4) {
            Text("Don't have an account?")
                .font(CawnexTypography.caption)
                .foregroundStyle(CawnexColors.mutedForeground)
            Button {
                // TBD: registration flow
            } label: {
                Text("Sign Up")
                    .font(.custom("Inter", size: 13).weight(.semibold))
                    .foregroundStyle(CawnexColors.primaryLight)
            }
        }
    }
}

#Preview {
    SignInScreen(onSignIn: {})
}
