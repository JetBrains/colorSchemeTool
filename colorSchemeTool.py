from __future__ import division
import colorsys
import xml.etree.cElementTree as ET
import plistlib
import os.path
import sys

default_attributes = {}
all_attributes = []
all_colors = {}
IGNORE_COLOR = (None, None, None)
IGNORE_COLOR_VALUE = "IGNORE_COLOR"

# http://effbot.org/zone/element-lib.htm#prettyprint
def indent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def hex_to_rgb(color):
    r = int(color[0:2], 16) / 256
    g = int(color[2:4], 16) / 256 if len(color) >= 4 else 0
    b = int(color[4:6], 16) / 256 if len(color) >= 6 else 0
    return r, g, b

def rgb256_to_hex(r, g, b):
    return "{0:02x}{1:02x}{2:02x}".format(r, g, b)

def rgb_to_hex(r, g, b):
    r = min(int(r * 256), 255)
    g = min(int(g * 256), 255)
    b = min(int(b * 256), 255)
    return rgb256_to_hex(r, g, b)

class AttributeValue:
    def __init__(self, foreground=None, background=None, foreground_rgb=None, background_rgb=None,
                 font_style=0, effect_type=0):
        if foreground_rgb:
            self.foreground = rgb256_to_hex(*foreground_rgb)
        else:
            self.foreground = foreground
        if background_rgb:
            self.background = rgb256_to_hex(*background_rgb)
        else:
            self.background = background
        self.font_style = font_style
        self.error_stripe = None
        self.effect_color = None
        self.effect_type = effect_type
        self.inherited = False

class DerivedAttributeValue:
    def __init__(self, parent=None, default_fore=None, default_back=None, default_font=0, error_stripe=None):
        self.parent = parent
        self.default_fore = default_fore
        self.default_back = default_back
        self.default_font = default_font
        self.default_effect_color = None
        self.error_stripe = error_stripe
        self.effect_type = None

    @property
    def inverted(self):
        p = self.parent
        while not p.value.background:
            p = p.parent
        py, pi, pq = colorsys.rgb_to_yiq(*hex_to_rgb(p.value.background))
        return py < 0.5

    @property
    def inherited(self):
        return self.parent.id != 'TEXT' and isinstance(self.parent.value, AttributeValue)

    def transform(self, default_value, add_luma=0.0):
        if self.inverted:
            dy, di, dq = colorsys.rgb_to_yiq(*hex_to_rgb(default_value))
            dy = 1 - dy
            if dy < 0.5:
                dy += add_luma
            r, g, b = colorsys.yiq_to_rgb(dy, di, dq)
            return rgb_to_hex(r, g, b)
        return default_value

    @property
    def foreground(self):
        if self.inherited:
            return self.parent.value.foreground
        if self.default_fore:
            return self.transform(self.default_fore)
        if self.parent.id != "TEXT":
            return self.parent.value.foreground
        return None

    @property
    def background(self):
        if self.inherited:
            return self.parent.value.background
        if self.default_back:
            return self.transform(self.default_back, 0 if self.default_fore else 0.15)
        if self.parent.id != "TEXT":
            return self.parent.value.background
        return None

    @property
    def font_style(self):
        return self.parent.value.font_style | self.default_font

    @property
    def effect_color(self):
        if self.inherited:
            return self.parent.value.effect_color
        if self.default_effect_color:
            return self.transform(self.default_effect_color)
        if self.parent.id != "TEXT":
            return self.parent.value.effect_color
        return None

class Attribute:
    def __init__(self, id, parent, scope=None, foreground=None, background=None, font_style=0, effect_type=None):
        self.id = id
        self.parent = parent
        self.scope = scope
        if default_attributes.has_key(id):
            self.value = default_attributes[id]
            self.value.parent = parent
        else:
            self.value = DerivedAttributeValue(parent=parent)
            if foreground:
                self.value.default_fore = rgb256_to_hex(*foreground) if foreground != IGNORE_COLOR else IGNORE_COLOR_VALUE
            if background:
                self.value.default_back = rgb256_to_hex(*background) if background != IGNORE_COLOR else IGNORE_COLOR_VALUE
            if font_style:
                self.value.default_font = font_style
            if effect_type:
                self.value.effect_type = effect_type
        all_attributes.append(self)

text = Attribute("TEXT", None)

def load_default_attributes(scheme_path):
    scheme = ET.ElementTree(file=scheme_path)
    attributes = scheme.findall('.//attributes/option')
    for attr in attributes:
        name = attr.attrib.get('name')
        options = attr.findall('./value/option')
        attr_value = DerivedAttributeValue()
        for option in options:
            option_name = option.attrib.get('name')
            option_value = option.attrib.get('value')
            if not option_value: continue
            if option_name == 'FOREGROUND': attr_value.default_fore = option_value
            if option_name == 'BACKGROUND': attr_value.default_back = option_value
            if option_name == 'FONT_TYPE': attr_value.default_font = int(option_value)
            if option_name == 'ERROR_STRIPE_COLOR': attr_value.error_stripe = option_value
            if option_name == 'EFFECT_TYPE': attr_value.effect_type = int(option_value)
            if option_name == 'EFFECT_COLOR': attr_value.default_effect_color = option_value
            default_attributes[name] = attr_value

load_default_attributes('DefaultColorSchemesManager.xml')

for id in ["FOLDED_TEXT_ATTRIBUTES",
           "SEARCH_RESULT_ATTRIBUTES",                # EditorColors
           "WRITE_SEARCH_RESULT_ATTRIBUTES",
           "IDENTIFIER_UNDER_CARET_ATTRIBUTES",
           "WRITE_IDENTIFIER_UNDER_CARET_ATTRIBUTES",
           "TEXT_SEARCH_RESULT_ATTRIBUTES",
           "INJECTED_LANGUAGE_FRAGMENT",
           "ERRORS_ATTRIBUTES",                       # CodeInsightColors
           "WARNING_ATTRIBUTES",
           "GENERIC_SERVER_ERROR_OR_WARNING",
           "DUPLICATE_FROM_SERVER",
           "INFO_ATTRIBUTES",
           "NOT_USED_ELEMENT_ATTRIBUTES",
           "DEPRECATED_ATTRIBUTES",
           "HYPERLINK_ATTRIBUTES",
           "FOLLOWED_HYPERLINK_ATTRIBUTES",
           "TODO_DEFAULT_ATTRIBUTES",
           "CONSOLE_NORMAL_OUTPUT",                   # ConsoleViewContentType
           "CONSOLE_ERROR_OUTPUT", 
           "CONSOLE_USER_INPUT",
           "CONSOLE_SYSTEM_OUTPUT",
           "DIFF_MODIFIED",                           # DiffColors
           "DIFF_DELETED",
           "DIFF_INSERTED",
           "DIFF_CONFLICT",
           "CUSTOM_KEYWORD1_ATTRIBUTES",              # CustomHighlighterColors
           "CUSTOM_KEYWORD2_ATTRIBUTES",
           "CUSTOM_KEYWORD3_ATTRIBUTES",
           "CUSTOM_KEYWORD4_ATTRIBUTES",
           "BREAKPOINT_ATTRIBUTES",                   # DebuggerColors
           "EXECUTIONPOINT_ATTRIBUTES"
          ]:
    Attribute(id, text)

# HighlighterColors
bad_character = Attribute("BAD_CHARACTER", text, scope='invalid')

# CodeInsightColors
instance_field = Attribute("INSTANCE_FIELD_ATTRIBUTES", text)
static_field = Attribute("STATIC_FIELD_ATTRIBUTES", text)
static_method = Attribute("STATIC_METHOD_ATTRIBUTES", text)

# SyntaxHighlighterColors
line_comment = Attribute("JAVA_LINE_COMMENT", text, scope='comment.line')
block_comment = Attribute("JAVA_BLOCK_COMMENT", line_comment, scope='comment.block')
doc_comment = Attribute("JAVA_DOC_COMMENT", line_comment, scope='comment.documentation')
keyword = Attribute("JAVA_KEYWORD", text, scope='keyword')
number = Attribute("JAVA_NUMBER", text, scope='constant.numeric')
string = Attribute("JAVA_STRING", text, scope='string')
opSign = Attribute("JAVA_OPERATION_SIGN", text, scope='keyword.operator')
parenths = Attribute("JAVA_PARENTH", text, scope='punctuation')
brackets = Attribute("JAVA_BRACKETS", text, scope='punctuation')
braces = Attribute("JAVA_BRACES", text, scope='punctuation')
comma = Attribute("JAVA_COMMA", text, scope='punctuation')
dot = Attribute("JAVA_DOT", text, scope='punctuation')
semicolon = Attribute("JAVA_SEMICOLON", text, scope='punctuation')
valid_string_escape = Attribute("JAVA_VALID_STRING_ESCAPE", text, scope='constant.character.escape')
invalid_string_escape = Attribute("JAVA_INVALID_STRING_ESCAPE", text, scope='invalid')
doc_comment_tag = Attribute("JAVA_DOC_TAG", text)
doc_comment_markup = Attribute("JAVA_DOC_MARKUP", text)

# XmlHighlighterColors
xml_prologue = Attribute("XML_PROLOGUE", text)
xml_comment = Attribute("XML_COMMENT", block_comment)
xml_tag = Attribute("XML_TAG", text, scope='meta.tag')
xml_tag_name = Attribute("XML_TAG_NAME", text, scope='entity.name.tag')
xml_attribute_name = Attribute("XML_ATTRIBUTE_NAME", text, scope='entity.other.attribute-name')
xml_attribute_value = Attribute("XML_ATTRIBUTE_VALUE", text, scope='string.quoted.double')
xml_tag_data = Attribute("XML_TAG_DATA", text)
xml_entity_reference = Attribute("XML_ENTITY_REFERENCE", text, scope='constant.character.entity')

html_comment = Attribute("HTML_COMMENT", xml_comment)
html_tag = Attribute("HTML_TAG", xml_tag)
html_tag_name = Attribute("HTML_TAG_NAME", xml_tag_name)
html_attribute_name = Attribute("HTML_ATTRIBUTE_NAME", xml_attribute_name)
html_attribute_value = Attribute("HTML_ATTRIBUTE_VALUE", xml_attribute_value)
html_entity_reference = Attribute("HTML_ENTITY_REFERENCE", xml_entity_reference)

# PyHighlighter
py_keyword = Attribute("PY.KEYWORD", keyword)
py_string = Attribute("PY.STRING", string)
py_number = Attribute("PY.NUMBER", number)
py_comment = Attribute("PY.LINE_COMMENT", line_comment)
py_opSign = Attribute("PY.OPERATION_SIGN", opSign)
py_parenths = Attribute("PY.PARENTHS", parenths)
py_brackets = Attribute("PY.BRACKETS", brackets)
py_braces = Attribute("PY.BRACES", braces)
py_comma = Attribute("PY.COMMA", comma)
py_dot = Attribute("PY.DOT", dot)
py_doc_comment = Attribute("PY.DOC_COMMENT", doc_comment)

py_decorator = Attribute("PY.DECORATOR", text, scope='entity.name.function.decorator')
py_class_def = Attribute("PY.CLASS_DEFINITION", text, scope='entity.name.class')
py_func_def = Attribute("PY.FUNC_DEFINITION", text, scope='entity.name.function')
py_predef_def = Attribute("PY.PREDEFINED_DEFINITION", text)  # scope???
py_predef_usage = Attribute("PY.PREDEFINED_USAGE", text, scope='support.function')
py_builtin_name = Attribute("PY.BUILTIN_NAME", text, scope='support.function')
py_valid_string_escape = Attribute("PY.VALID_STRING_ESCAPE", valid_string_escape)
py_invalid_string_escape = Attribute("PY.INVALID_STRING_ESCAPE", invalid_string_escape)

# DjangoTemplateHighlighter
dj_comment = Attribute("DJANGO_COMMENT", html_comment)
dj_tag_name = Attribute("DJANGO_TAG_NAME", xml_tag_name)
dj_id = Attribute("DJANGO_ID", xml_attribute_name)
dj_string_literal = Attribute("DJANGO_STRING_LITERAL", xml_attribute_value)
dj_keyword = Attribute("DJANGO_KEYWORD", keyword)
dj_number = Attribute("DJANGO_NUMBER", number)
dj_tag_start_end = Attribute("DJANGO_TAG_START_END", braces)
dj_filter = Attribute("DJANGO_FILTER", braces, scope='support.function')

# Gql
gql_string_literal = Attribute("GQL_STRING_LITERAL", string)
gql_keyword = Attribute("GQL_KEYWORD", keyword)
gql_int_literal = Attribute("GQL_INT_LITERAL", number)
gql_id =Attribute("GQL_ID", number)

# BuildoutCfgSyntaxHighlighter
bld_section_name = Attribute("BUILDOUT.SECTION_NAME", number)
bld_key = Attribute("BUILDOUT.KEY", keyword)
bld_value = Attribute("BUILDOUT.VALUE", string)
bld_comment = Attribute("BUILDOUT.LINE_COMMENT", line_comment)
bld_separator = Attribute("BUILDOUT.KEY_VALUE_SEPARATOR", opSign)

# RegExp
rx_meta = Attribute("REGEXP.META", keyword)
rx_invalid_escape = Attribute("REGEXP.INVALID_STRING_ESCAPE", invalid_string_escape)
rx_bad_character = Attribute("REGEXP.BAD_CHARACTER", bad_character)
rx_redundant_escape = Attribute("REGEXP.REDUNDANT_ESCAPE", valid_string_escape)
rx_parenths = Attribute("REGEXP.PARENTHS", parenths)
rx_braces = Attribute("REGEXP.BRACES", braces)
rx_brackets = Attribute("REGEXP.BRACKETS", brackets)
rx_comma = Attribute("REGEXP.COMMA", comma)
rx_esc_character = Attribute("REGEXP.ESC_CHARACTER", valid_string_escape)
rx_char_class = Attribute("REGEXP.CHAR_CLASS", valid_string_escape)
rx_quote_character = Attribute("REGEXP.QUOTE_CHARACTER", valid_string_escape)
rx_comment = Attribute("REGEXP.COMMENT", line_comment)

# CSS
css_ident = Attribute("CSS.IDENT", html_tag_name, scope='meta.selector.css')
css_comment = Attribute("CSS.COMMENT", html_comment)
css_property_name = Attribute("CSS.PROPERTY_NAME", html_attribute_name, scope='support.type.property-name')
css_property_value = Attribute("CSS.PROPERTY_VALUE", html_attribute_value)
css_tag_name = Attribute("CSS.TAG_NAME", html_tag_name)
css_string = Attribute("CSS.STRING", string)
css_number = Attribute("CSS.NUMBER", number, scope='constant.numeric.css')
css_keyword = Attribute("CSS.KEYWORD", keyword)
css_function = Attribute("CSS.FUNCTION", html_tag_name)
css_url = Attribute("CSS.URL", html_attribute_value)

# LESS
less_variable = Attribute("LESS_VARIABLE", text, foreground=(104, 12, 122), font_style=1)

# SASS
sass_rule = Attribute("SASS_RULE", keyword)
sass_attribute = Attribute("SASS_ATTRIBUTE", keyword)
sass_constant = Attribute("SASS_CONSTANT", keyword, scope='constant', foreground=(128, 0, 128), font_style=1)
sass_string = Attribute("SASS_STRING", string)
sass_directive = Attribute("SASS_DIRECTIVE", keyword, foreground=(0, 0, 255))
sass_mixin = Attribute("SASS_MIXIN", keyword, foreground=(0, 128, 128))
sass_comment = Attribute("SASS_COMMENT", line_comment)
sass_number = Attribute("SASS_NUMBER", number)

# JS
js_keyword = Attribute("JS.KEYWORD", keyword)
js_string = Attribute("JS.STRING", string)
js_number = Attribute("JS.NUMBER", number)
js_regexp = Attribute("JS.REGEXP", text, scope='string.regexp')
js_line_comment = Attribute("JS.LINE_COMMENT", line_comment)
js_block_comment = Attribute("JS.BLOCK_COMEMNT", block_comment)
js_doc_comment = Attribute("JS.DOC_COMMENT", doc_comment)
js_opSign = Attribute("JS.OPERATION_SIGN", opSign)
js_parenths = Attribute("JS.PARENTHS", parenths)
js_brackets = Attribute("JS.BRACKETS", brackets)
js_braces = Attribute("JS.BRACES", braces)
js_comma = Attribute("JS.COMMA", comma)
js_dot = Attribute("JS.DOT", dot)
js_semicolon = Attribute("JS.SEMICOLON", semicolon)
js_badchar = Attribute("JS.BADCHARACTER", bad_character)
js_doc_tag = Attribute("JS.DOC_TAG", doc_comment_tag)
js_doc_markup = Attribute("JS.DOC_MARKUP", doc_comment_markup)
js_valid_escape = Attribute("JS.VALID_STRING_ESCAPE", valid_string_escape)
js_invalid_escape = Attribute("JS.INVALID_STRING_ESCAPE", invalid_string_escape)
js_local_var = Attribute("JS.LOCAL_VARIABLE", text, foreground=(69, 131, 131))
js_parameter = Attribute("JS.PARAMETER", text, effect_type=1, scope='variable.parameter')
js_instance_member_var = Attribute("JS.INSTANCE_MEMBER_VARIABLE", instance_field)
js_static_member_var = Attribute("JS.STATIC_MEMBER_VARIABLE", static_field)
js_global_var = Attribute("JS.GLOBAL_VARIABLE", static_field)
js_global_function = Attribute("JS.GLOBAL_FUNCTION", static_method)
js_static_member_func = Attribute("JS.STATIC_MEMBER_FUNCTION", static_method)
js_instance_member_func = Attribute("JS.INSTANCE_MEMBER_FUNCTION", text, foreground=(0x7a, 0x7a, 43))
js_attr = Attribute("JS.ATTRIBUTE", text, background=(0xf7, 0xe9, 0xe9))

# YAML
yaml_scalar_key = Attribute("YAML_SCALAR_KEY", keyword)
yaml_scalar_value = Attribute("YAML_SCALAR_VALUE", text)
yaml_scalar_string = Attribute("YAML_SCALAR_STRING", text, foreground=(0, 128, 128), font_style=1)
yaml_scalar_dstring = Attribute("YAML_SCALAR_DSTRING", text, foreground=(0, 128, 0), font_style=1)
yaml_scalar_list = Attribute("YAML_SCALAR_LIST", text, background=(218, 233, 246))
yaml_text = Attribute("YAML_TEXT", text)
yaml_sign = Attribute("YAML_SIGN", opSign)


# RubyHighlighter
rb_keyword = Attribute("RUBY_KEYWORD", keyword)
rb_comment = Attribute("RUBY_COMMENT", line_comment)
rb_heredoc_id = Attribute("RUBY_HEREDOC_ID", text, scope="string.quoted.double.ruby")
rb_number = Attribute("RUBY_NUMBER", number)
rb_string = Attribute("RUBY_STRING", string)
rb_escape_sequence = Attribute("RUBY_ESCAPE_SEQUENCE", valid_string_escape)
rb_invalid_escape_sequence = Attribute("RUBY_INVALID_ESCAPE_SEQUENCE", invalid_string_escape)
rb_opSign = Attribute("RUBY_OPERATION_SIGN", opSign)
rb_brackets = Attribute("RUBY_BRACKETS", brackets)
rb_expr_in_string = Attribute("RUBY_EXPR_IN_STRING", string, scope='string source')
rb_bad_character = Attribute("RUBY_BAD_CHARACTER", text, scope='invalid')
rb_regexp = Attribute("RUBY_REGEXP", string, scope='string.regexp')
rb_words = Attribute("RUBY_WORDS", string)
rb_heredoc = Attribute("RUBY_HEREDOC_CONTENT", string, scope='string.unquoted')
rb_identifier = Attribute("RUBY_IDENTIFIER", text, scope='variable')
rb_method_name = Attribute("RUBY_METHOD_NAME", rb_identifier, scope='entity.name.function')
rb_constant = Attribute("RUBY_CONSTANT", rb_identifier, scope='constant')
rb_gvar = Attribute("RUBY_GVAR", rb_identifier, scope='variable.other.readwrite.global')
rb_cvar = Attribute("RUBY_CVAR", rb_identifier, scope='variable.other.readwrite.class')
rb_ivar = Attribute("RUBY_IVAR", rb_identifier, scope='variable.other.readwrite.instance')
rb_nth_ref = Attribute("RUBY_NTH_REF", text)
rb_comma = Attribute("RUBY_COMMA", comma)
rb_semicolon = Attribute("RUBY_SEMICOLON", semicolon)
rb_hash_assoc = Attribute("RUBY_HASH_ASSOC", opSign, scope='punctuation.separator.key-value')
rb_line_continuation = Attribute("RUBY_LINE_CONTINUATION", opSign)
rb_local_var = Attribute("RUBY_LOCAL_VAR_ID", rb_identifier)
rb_parameter = Attribute("RUBY_PARAMETER_ID", rb_identifier, scope='variable.parameter')
rb_symbol = Attribute("RUBY_SYMBOL", rb_identifier, scope='constant.other.symbol')
rb_specific_call = Attribute("RUBY_SPECIFIC_CALL", rb_identifier, scope='storage')
rb_paramdef = Attribute("RUBY_PARAMDEF_CALL", rb_identifier, scope='support.function')

# HAML
haml_text = Attribute("HAML_TEXT", text, scope='text.haml')
haml_tag_name = Attribute("HAML_TAG", haml_text, scope='meta.tag.haml')
haml_class = Attribute("HAML_CLASS", haml_text, scope='entity.name.tag.class.haml')
haml_id = Attribute("HAML_ID", haml_text, scope='entity.name.tag.id.haml')
haml_comment = Attribute("HAML_COMMENT", line_comment, scope='comment.line.slash.haml')
haml_xhtml = Attribute("HAML_XHTML", haml_text, scope='meta.prolog.haml')
haml_code_injection = Attribute("HAML_RUBY_CODE", haml_text, scope='source.ruby.embedded.haml', foreground=IGNORE_COLOR)
haml_ruby_evaluator = Attribute("HAML_RUBY_START", haml_text, scope='meta.line.ruby.haml')
haml_line_continuation = Attribute("HAML_LINE_CONTINUATION", haml_text)
haml_filter = Attribute("HAML_FILTER", haml_text)
haml_filter_content = Attribute("HAML_FILTER_CONTENT", haml_text)

# Cucumber (Gherkin)
cucumber_text = Attribute("GHERKIN_TEXT", text, scope='text.cucumber.feature')
cucumber_text = Attribute("GHERKIN_COMMENT", line_comment, scope='comment.line.number-sign')
cucumber_text = Attribute("GHERKIN_KEYWORD", keyword, scope='keyword.language.cucumber.feature')
#cucumber_text = Attribute("GHERKIN_KEYWORD_PENDING", cucumber_text, scope='keyword.language.cucumber.feature.scenario.pending.line')
#cucumber_text = Attribute("GHERKIN_KEYWORD_EXAMPLES", cucumber_text, scope='keyword.language.cucumber.feature.scenario.line')
#cucumber_text = Attribute("GHERKIN_KEYWORD_FEATURE", cucumber_text, scope='keyword.language.cucumber.feature')
#cucumber_text = Attribute("GHERKIN_KEYWORD_SCENARIO", cucumber_text, scope='keyword.language.cucumber.feature.scenario')
#cucumber_text = Attribute("GHERKIN_KEYWORD_SCENARIO_OUTLINE", cucumber_text, scope='keyword.language.cucumber.feature.scenario_outline')
cucumber_text = Attribute("GHERKIN_TAG", cucumber_text, scope='storage.type.tag.cucumber')
cucumber_text = Attribute("GHERKIN_PYSTRING", string, scope='string.quoted.single')
cucumber_table_header = Attribute("GHERKIN_TABLE_HEADER_CELL", cucumber_text, scope='variable.other')
cucumber_table_cell = Attribute("GHERKIN_TABLE_CELL", cucumber_text, scope='source.cucumber')
cucumber_table_pipe = Attribute("PIPE", semicolon, scope='keyword.control.cucumber.table')
cucumber_outline_param_substitution = Attribute("GHERKIN_OUTLINE_PARAMETER_SUBSTITUTION", cucumber_text, scope='variable.other')
cucumber_scenario_regexp_param = Attribute("GHERKIN_REGEXP_PARAMETER", cucumber_text, scope='string.quoted.double')

# ERB : "text.html.ruby"
erb_text = xml_tag
erb_block_start = Attribute("RHTML_SCRIPTLET_START_ID", erb_text, scope='punctuation.section.embedded.ruby')
erb_block_end = Attribute("RHTML_SCRIPTLET_END_ID", erb_text, scope='punctuation.section.embedded.ruby')
erb_block_expression_start = Attribute("RHTML_EXPRESSION_START_ID", erb_text, scope='punctuation.section.embedded.ruby')
erb_block_expression_end = Attribute("RHTML_EXPRESSION_END_ID", erb_text, scope='punctuation.section.embedded.ruby')
erb_comment = Attribute("RHTML_COMMENT_ID", line_comment, scope='comment.block.erb')
erb_omit_line_modifier = Attribute("RHTML_OMIT_NEW_LINE_ID", erb_text, scope='punctuation.section.embedded.ruby')
erb_ruby_injection_bg = Attribute("RHTML_SCRIPTING_BACKGROUND_ID", erb_text, scope='source.ruby.rails.embedded.html', foreground=IGNORE_COLOR)

# CustomHighlighter
custom_number = Attribute("CUSTOM_NUMBER_ATTRIBUTES", number)
custom_string = Attribute("CUSTOM_STRING_ATTRIBUTES", string)
custom_line_comment = Attribute("CUSTOM_LINE_COMMENT_ATTRIBUTES", line_comment)
custom_multi_line_comment = Attribute("CUSTOM_MULTI_LINE_COMMENT_ATTRIBUTES", doc_comment)
custom_valid_string_escape = Attribute("CUSTOM_VALID_STRING_ESCAPE_ATTRIBUTES", valid_string_escape)
custom_invalid_string_escape = Attribute("CUSTOM_INVALID_STRING_ESCAPE_ATTRIBUTES", invalid_string_escape)

def color_from_textmate(color, alpha_blend_with=None):
    rgba = color[1:]
    if len(rgba) == 8 and alpha_blend_with:
        r, g, b = hex_to_rgb(rgba[:6])
        rb, gb, bb = hex_to_rgb(alpha_blend_with[1:])
        alpha = int(rgba[6:8], 16) / 256
        r = r * alpha + rb * (1-alpha)
        g = g * alpha + gb * (1-alpha)
        b = b * alpha + bb * (1-alpha)
        return rgb_to_hex(r, g, b)
    return rgba[:6]

def font_style_from_textmate(style):
    result = 0
    if 'italic' in style: result += 2
    return result

def attr_from_textmate(settings, old_value):
    result = AttributeValue()

    if ('foreground' in settings) and ((old_value == None) or (old_value.default_fore != IGNORE_COLOR_VALUE)):
        result.foreground = color_from_textmate(settings['foreground'])

    if ('background' in settings) and ((old_value == None) or (old_value.default_back != IGNORE_COLOR_VALUE)):
        result.background = color_from_textmate(settings['background'])

    if 'fontStyle' in settings:
        tm_font_style = settings['fontStyle']
        result.font_style = font_style_from_textmate(tm_font_style)
        if 'underline' in tm_font_style:
            result.effect_type = 1
    return result

def find_by_scope(settings, scope):
    less_specific = None
    for setting in settings:
        scope_of_setting = setting.get('scope', None)
        if scope_of_setting is None:
            if scope is None: return setting
        else:
            scopes_of_setting = scope_of_setting.split(",")
            for aScope in scopes_of_setting:
                aScope = aScope.strip()
                chain = aScope.split(' ')
                aScope = chain[-1]
                if aScope.startswith(scope):
                    return setting
                if scope.startswith(aScope):
                    less_specific = setting
    return less_specific

def load_textmate_scheme(tmtheme):
    themeDict = plistlib.readPlist(tmtheme)
    all_settings = themeDict['settings']
    used_scopes = set()
    default_settings = find_by_scope(all_settings, None)
    if not default_settings:
        print "Cannot find default settings"
        return
    default_settings = default_settings['settings']

    text.value = attr_from_textmate(default_settings, None)

    background = default_settings['background']

    all_colors['CARET_COLOR'] = color_from_textmate(default_settings['caret'])
    all_colors['CARET_ROW_COLOR'] = color_from_textmate(default_settings['lineHighlight'], background)
    all_colors['INDENT_GUIDE'] = color_from_textmate(default_settings['invisibles'], background)
    all_colors['WHITESPACES'] = color_from_textmate(default_settings['invisibles'], background)
    all_colors['SELECTION_BACKGROUND'] = color_from_textmate(default_settings['selection'], background)
    all_colors['CONSOLE_BACKGROUND_KEY'] = text.value.background

    for attr in all_attributes:
        if attr.scope:
            settings = find_by_scope(all_settings, attr.scope)
            if settings:
                the_scope = settings['scope']
                if the_scope:
                    print "converting attribute " + attr.id + " from TextMate scope " + the_scope
                    used_scopes.add(the_scope)
                attr.value = attr_from_textmate(settings['settings'], attr.value)
    return all_settings, used_scopes

def write_idea_scheme(filename):
    name, ext = os.path.splitext(os.path.basename(filename))
    scheme = ET.Element("scheme", name=name, version="1", parent_scheme="Default")
    ET.SubElement(scheme, 'option', name='LINE_SPACING', value='1.0')
    ET.SubElement(scheme, 'option', name='EDITOR_FONT_SIZE', value='12')
    ET.SubElement(scheme, 'option', name='EDITOR_FONT_NAME', value='Monaco')
    colors = ET.SubElement(scheme, 'colors')
    for name, value in all_colors.iteritems():
        ET.SubElement(colors, 'option', name=name, value=value)
    attributes = ET.SubElement(scheme, 'attributes')
    for attr in all_attributes:
        if attr.value.inherited:
            print 'inheriting ' + attr.id + ' from ' + attr.parent.id
        elif isinstance(attr.value, DerivedAttributeValue):
            print 'transforming IDEA default color for ' + attr.id
        option = ET.SubElement(attributes, 'option', name=attr.id)
        value = ET.SubElement(option, 'value')
        fore = attr.value.foreground
        if fore and (fore != IGNORE_COLOR_VALUE): ET.SubElement(value, 'option', name='FOREGROUND', value=fore)
        back = attr.value.background
        if back and (back != IGNORE_COLOR_VALUE): ET.SubElement(value, 'option', name='BACKGROUND', value=back)
        if attr.value.font_style:
            ET.SubElement(value, 'option', name='FONT_TYPE', value=str(attr.value.font_style))
        if attr.value.effect_type:
            ET.SubElement(value, 'option', name='EFFECT_TYPE', value=str(attr.value.effect_type))
            if attr.value.effect_color:
                ET.SubElement(value, 'option', name='EFFECT_COLOR', value=attr.value.effect_color)                
            elif fore:
                ET.SubElement(value, 'option', name='EFFECT_COLOR', value=fore)
            else:
                ET.SubElement(value, 'option', name='EFFECT_COLOR', value=text.value.foreground)
        if attr.value.error_stripe:
            ET.SubElement(value, 'option', name='ERROR_STRIPE_COLOR', value=attr.value.error_stripe)
    indent(scheme)
    ET.ElementTree(scheme).write(filename)

if len(sys.argv) != 3:
    print 'Usage: colorSchemeTool <TextMate scheme> <IDEA/PyCharm/RubyMine scheme>'
    exit(1)

all_settings, used_scopes = load_textmate_scheme(sys.argv[1])
write_idea_scheme(sys.argv[2])



for setting in all_settings:
    scope = setting.get('scope', None)
    if scope and not scope in used_scopes:
        print "Unused scope: " + scope