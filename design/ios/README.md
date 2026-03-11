# iOS Design Files (.pen)

Design files for the Cawnex iOS app using [Pencil](https://pencil.dev)'s `.pen` format.

## Structure

```
design/ios/
├── design-system/     ← Tokens, typography, color palette
│   └── tokens.pen     ← Foundation design tokens (light/dark)
├── components/        ← Reusable component definitions
│   └── *.pen          ← One per component family
└── screens/           ← Full screen designs
    ├── S01-splash.pen
    ├── S02-sign-in.pen
    ├── S10-project-list.pen
    ├── S12-vision-chat.pen
    └── ...
```

## Naming Convention

- Screens: `S{number}-{kebab-name}.pen` (e.g., `S12-vision-chat.pen`)
- Components: `{component-name}.pen` (e.g., `crow-badge.pen`)
- Design system: `tokens.pen`, `typography.pen`, `icons.pen`
