/** @type {import("@commitlint/types").UserConfig} */
const config = {
  extends: ["@commitlint/config-conventional"],
  plugins: [
    {
      rules: {
        "no-ai-attribution": ({ raw }) => {
          const coAuthorPattern = /Co-Authored-By:/i
          const aiPattern =
            /(🤖 Generated|Claude|Paperclip|claude-code|noreply@anthropic\.com|noreply@paperclip\.ing)/i

          if (coAuthorPattern.test(raw)) {
            return [false, "Commit message must not contain \"Co-Authored-By:\" lines"]
          }
          if (aiPattern.test(raw)) {
            return [
              false,
              "Commit message must not contain AI-attribution markers (Claude, Paperclip, Generated, etc.)",
            ]
          }
          return [true, ""]
        },
      },
    },
  ],
  rules: {
    "subject-case": [2, "always", "lower-case"],
    "subject-max-length": [2, "always", 72],
    "body-max-line-length": [2, "always", 100],
    "no-ai-attribution": [2, "always"],
  },
}

module.exports = config

