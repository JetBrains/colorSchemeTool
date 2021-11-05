[![JetBrains team project](http://jb.gg/badges/team.svg)](https://confluence.jetbrains.com/display/ALL/JetBrains+on+GitHub)
# colorSchemeTool for JetBrains IDEs
This tool can help you convert color schemes used in TextMate and VS Code and make them compatible with IntelliJ-based IDEs, such as IntelliJ IDEA, WebStorm, and PyCharm.

Please note that converted color schemes may not look 100% precise because of the differences between the tools. If you spot any significant issues or encounter a problem, please report them [here](https://github.com/JetBrains/colorSchemeTool/issues).

Note that the tool requires Node.js and Python 3.

# How to convert VSCode theme
**Note:** please check if the desired theme already exists in the [JetBrains plugin repository](https://plugins.jetbrains.com/) before converting it.
1. Clone the `colorSchemeTool` code.
2. Download the JSON file with the VS Code theme you’d like to convert.
3. Move the JSON file to the `vscThemes` folder under `colorSchemeTool`.
4. Run the `convert.sh` script.
5. Check the `intellijThemes` folder – you should find a new `.icls` file there.


## How to apply converted theme
1. In your IDE, go to `Preferences / Settings | Editor | Color Scheme`.
2. Click on the `Show Scheme Actions` gear icon and select `Import Scheme...`.
3. Choose the newly converted `.icls` file.
