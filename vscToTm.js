const json5 = require('json5')
const plist = require('plist')
const fs = require('fs')

function convert(vscTheme) {
    const tmTheme = {
        settings: vscTheme.tokenColors
    }
    tmTheme.settings[0].settings.caret = vscTheme.colors["editorCursor.foreground"]
    tmTheme.settings[0].settings.invisibles = vscTheme.colors["editorWhitespace.foreground"]
    tmTheme.settings[0].settings.selection = vscTheme.colors["editor.selectionBackground"]
    tmTheme.settings[0].settings.lineHighlight = vscTheme.colors["editor.lineHighlightBackground"]
    for (i = 1; i < tmTheme.settings.length; i++) {
       const scope = tmTheme.settings[i].scope
       if (scope) {
           tmTheme.settings[i].scope = scope.toString()
       } 
    }
    return tmTheme
}

const vscTheme = json5.parse(fs.readFileSync(process.argv[2], "utf8"))
fs.writeFileSync(process.argv[3], plist.build(convert(vscTheme)))