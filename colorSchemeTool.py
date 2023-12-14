import colorsys
import xml.etree.cElementTree as ET
import plistlib
import os.path
import sys
import re

default_attributes = {}
all_attributes = []
all_colors = {}
IGNORE_COLOR = (None, None, None)
IGNORE_COLOR_VALUE = "#IGNORE_COLOR"

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

def capitalize_colors(elem):
    if len(elem):
        for elem in elem:
            if elem.get("value") is not None:
                elem.set("value", elem.get("value").upper())
            capitalize_colors(elem)

def hex_to_rgb(color):
    l = len(color)
    r = int(color[l-6:l-4], 16) / 256 if l >= 6 else 0
    g = int(color[l-4:l-2], 16) / 256 if l >= 4 else 0
    b = int(color[l-2:l], 16) / 256
    return r, g, b

def hex_to_yiq(color):
    return colorsys.rgb_to_yiq(*hex_to_rgb(color))

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
        py, pi, pq = hex_to_yiq(p.value.background)
        return py < 0.5

    @property
    def inherited(self):
        return self.parent.id != 'TEXT' and isinstance(self.parent.value, AttributeValue)

    def transform(self, default_value, add_luma=0.0):
        if default_value == IGNORE_COLOR_VALUE:
            return IGNORE_COLOR_VALUE
        if self.inverted:
            dy, di, dq = hex_to_yiq(default_value)
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
        if self.default_fore and self.default_fore != IGNORE_COLOR_VALUE:
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
        if id in default_attributes:
            self.value = default_attributes[id]
            if background == IGNORE_COLOR:
                self.value.default_back = IGNORE_COLOR_VALUE
            if foreground == IGNORE_COLOR:
                self.value.default_fore = IGNORE_COLOR_VALUE
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

for id in [
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
           "CONSOLE_RED_OUTPUT",
           "CONSOLE_GREEN_OUTPUT",
           "CONSOLE_YELLOW_OUTPUT",
           "CONSOLE_BLUE_OUTPUT",
           "CONSOLE_MAGENTA_OUTPUT",
           "CONSOLE_CYAN_OUTPUT",
           "CONSOLE_GRAY_OUTPUT",
           "CONSOLE_SYSTEM_OUTPUT",
           "CUSTOM_KEYWORD1_ATTRIBUTES",              # CustomHighlighterColors
           "CUSTOM_KEYWORD2_ATTRIBUTES",
           "CUSTOM_KEYWORD3_ATTRIBUTES",
           "CUSTOM_KEYWORD4_ATTRIBUTES",
           "BREAKPOINT_ATTRIBUTES"                   # DebuggerColors
          ]:
    Attribute(id, text)

# HighlighterColors
bad_character = Attribute("BAD_CHARACTER", text, scope='invalid')
matched_brace = Attribute("MATCHED_BRACE_ATTRIBUTES", text, background=(153, 204, 255))
unmatched_brace = Attribute("UNMATCHED_BRACE_ATTRIBUTES", text, background=(255, 220, 220))

# DefaultLanguageHighlighterColors (MUST HAVE!)
default_identifier=Attribute("DEFAULT_IDENTIFIER", text, scope='entity')
default_number=Attribute("DEFAULT_NUMBER", text, scope='constant.numeric')
default_keyword=Attribute("DEFAULT_KEYWORD", text, scope='keyword')
default_string=Attribute("DEFAULT_STRING", text, scope='string')
default_block_comment=Attribute("DEFAULT_BLOCK_COMMENT", text, scope='comment.block')
default_line_comment=Attribute("DEFAULT_LINE_COMMENT", text, scope='comment.line')
default_doc_comment=Attribute("DEFAULT_DOC_COMMENT", text, scope='comment.documentation')
default_operation_sign=Attribute("DEFAULT_OPERATION_SIGN", text, scope='keyword.operator')
default_braces=Attribute("DEFAULT_BRACES", text, scope='punctuation')
default_dot=Attribute("DEFAULT_DOT", text, scope='punctuation')
default_semicolon=Attribute("DEFAULT_SEMICOLON", text, scope='punctuation')
default_comma=Attribute("DEFAULT_COMMA", text, scope='punctuation')
default_parentheses=Attribute("DEFAULT_PARENTHS", text, scope='punctuation')
default_brackets=Attribute("DEFAULT_BRACKETS", text, scope='punctuation')
default_label=Attribute("DEFAULT_LABEL", default_identifier)
default_constant=Attribute("DEFAULT_CONSTANT", default_identifier, scope='constant')
default_local_variable=Attribute("DEFAULT_LOCAL_VARIABLE", default_identifier, scope='variable')
default_global_variable=Attribute("DEFAULT_GLOBAL_VARIABLE", default_local_variable, font_style=2)
default_function_declaration=Attribute("DEFAULT_FUNCTION_DECLARATION", default_identifier, scope='entity.name.function')
default_function_call=Attribute("DEFAULT_FUNCTION_CALL", default_identifier, scope='support.function')
default_parameter=Attribute("DEFAULT_PARAMETER", default_identifier, scope='variable.parameter')
default_class_name=Attribute("DEFAULT_CLASS_NAME", default_identifier, scope='entity.name')
default_interface_name=Attribute("DEFAULT_INTERFACE_NAME", default_class_name)
default_instance_method=Attribute("DEFAULT_INSTANCE_METHOD", default_function_declaration)
default_instance_field=Attribute("DEFAULT_INSTANCE_FIELD", default_local_variable)
default_static_method=Attribute("DEFAULT_STATIC_METHOD", default_function_declaration)
default_static_field=Attribute("DEFAULT_STATIC_FIELD", default_global_variable)
default_doc_comment_markup=Attribute("DEFAULT_DOC_MARKUP", default_doc_comment)
default_doc_comment_tag=Attribute("DEFAULT_DOC_COMMENT_TAG", default_doc_comment)
default_valid_string_escape=Attribute("DEFAULT_VALID_STRING_ESCAPE", text, scope='constant.character.escape')
default_invalid_string_escape=Attribute("DEFAULT_INVALID_STRING_ESCAPE", text, scope='invalid')
default_predefined_symbol=Attribute("DEFAULT_PREDEFINED_SYMBOL", default_identifier, scope='support.type')
default_metadata=Attribute("DEFAULT_METADATA", text, scope='meta.tag')
default_markup_tag=Attribute("DEFAULT_TAG", text, scope='punctuation.definition.tag')
default_markup_attribute=Attribute("DEFAULT_ATTRIBUTE", default_identifier, scope='entity.other.attribute-name')
default_markup_entity=Attribute("DEFAULT_ENTITY", default_identifier, scope='constant.character.entity')
default_template_language=Attribute("DEFAULT_TEMPLATE_LANGUAGE_COLOR", text, scope='text source')

# CodeInsightColors (Java)
java_local_variable = Attribute("LOCAL_VARIABLE_ATTRIBUTES", text)
java_implicit_anonymous_class_parameter = Attribute("IMPLICIT_ANONYMOUS_CLASS_PARAMETER_ATTRIBUTES", text)
java_instance_field = Attribute("INSTANCE_FIELD_ATTRIBUTES", text)
java_static_field = Attribute("STATIC_FIELD_ATTRIBUTES", text)
java_static_method = Attribute("STATIC_METHOD_ATTRIBUTES", text)
java_parameter = Attribute("PARAMETER_ATTRIBUTES", text)
java_class_name = Attribute("CLASS_NAME_ATTRIBUTES", text)

# SyntaxHighlighterColors (Java)
java_line_comment = Attribute("JAVA_LINE_COMMENT", text, scope='comment.line')
java_block_comment = Attribute("JAVA_BLOCK_COMMENT", java_line_comment, scope='comment.block')
java_doc_comment = Attribute("JAVA_DOC_COMMENT", java_line_comment, scope='comment.documentation')
java_keyword = Attribute("JAVA_KEYWORD", text, scope='keyword')
java_number = Attribute("JAVA_NUMBER", text, scope='constant.numeric')
java_string = Attribute("JAVA_STRING", text, scope='string')
java_opSign = Attribute("JAVA_OPERATION_SIGN", text, scope='keyword.operator')
java_parenths = Attribute("JAVA_PARENTH", text, scope='punctuation')
java_brackets = Attribute("JAVA_BRACKETS", text, scope='punctuation')
java_braces = Attribute("JAVA_BRACES", text, scope='punctuation')
java_comma = Attribute("JAVA_COMMA", text, scope='punctuation')
java_dot = Attribute("JAVA_DOT", text, scope='punctuation')
java_semicolon = Attribute("JAVA_SEMICOLON", text, scope='punctuation')
java_valid_string_escape = Attribute("JAVA_VALID_STRING_ESCAPE", text, scope='constant.character.escape')
java_invalid_string_escape = Attribute("JAVA_INVALID_STRING_ESCAPE", text, scope='invalid')
java_doc_comment_tag = Attribute("JAVA_DOC_TAG", text)
java_doc_comment_markup = Attribute("JAVA_DOC_MARKUP", text)

# XmlHighlighterColors
xml_prologue = Attribute("XML_PROLOGUE", text)
xml_tag = Attribute("XML_TAG", text, scope='punctuation.definition.tag', background=IGNORE_COLOR)
xml_attribute_name = Attribute("XML_ATTRIBUTE_NAME", text, scope='entity.other.attribute-name.localname.xml')
xml_tag_name = Attribute("XML_TAG_NAME", text, scope='entity.name.tag.xml')
xml_attribute_value = Attribute("XML_ATTRIBUTE_VALUE", text, scope='string.quoted.double')
xml_tag_data = Attribute("XML_TAG_DATA", text)
xml_entity_reference = Attribute("XML_ENTITY_REFERENCE", text, scope='constant.character.entity')

html_comment = Attribute("HTML_COMMENT", default_block_comment, scope='comment.block.html')
html_tag = Attribute("HTML_TAG", xml_tag, scope='punctuation.definition.tag', background=IGNORE_COLOR)
html_tag_name = Attribute("HTML_TAG_NAME", xml_tag_name, scope="entity.name.tag")
html_attribute_name = Attribute("HTML_ATTRIBUTE_NAME", xml_attribute_name, scope="entity.other.attribute-name.html")
html_attribute_value = Attribute("HTML_ATTRIBUTE_VALUE", xml_attribute_value)
html_entity_reference = Attribute("HTML_ENTITY_REFERENCE", xml_entity_reference)

# PyHighlighter
py_keyword = Attribute("PY.KEYWORD", default_keyword, scope="storage.type")
py_string = Attribute("PY.STRING", default_string, 'string.quoted')
py_number = Attribute("PY.NUMBER", default_number)
py_comment = Attribute("PY.LINE_COMMENT", default_line_comment)
py_opSign = Attribute("PY.OPERATION_SIGN", default_operation_sign)
py_parenths = Attribute("PY.PARENTHS", default_parentheses)
py_brackets = Attribute("PY.BRACKETS", default_brackets)
py_braces = Attribute("PY.BRACES", default_braces)
py_comma = Attribute("PY.COMMA", default_comma)
py_dot = Attribute("PY.DOT", default_dot)
py_doc_comment = Attribute("PY.DOC_COMMENT", default_doc_comment)

py_decorator = Attribute("PY.DECORATOR", text, scope='entity.name.function.decorator')
py_class_def = Attribute("PY.CLASS_DEFINITION", text, scope='entity.name.class')
py_func_def = Attribute("PY.FUNC_DEFINITION", text, scope='entity.name.function')
py_predef_def = Attribute("PY.PREDEFINED_DEFINITION", text)  # scope???
py_predef_usage = Attribute("PY.PREDEFINED_USAGE", text, scope='support.function')
py_builtin_name = Attribute("PY.BUILTIN_NAME", text, scope='support.function')
py_valid_string_escape = Attribute("PY.VALID_STRING_ESCAPE", default_valid_string_escape)
py_invalid_string_escape = Attribute("PY.INVALID_STRING_ESCAPE", default_invalid_string_escape)

# DjangoTemplateHighlighter
dj_comment = Attribute("DJANGO_COMMENT", html_comment)
dj_tag_name = Attribute("DJANGO_TAG_NAME", xml_tag_name)
dj_id = Attribute("DJANGO_ID", xml_attribute_name)
dj_string_literal = Attribute("DJANGO_STRING_LITERAL", xml_attribute_value)
dj_keyword = Attribute("DJANGO_KEYWORD", default_keyword)
dj_number = Attribute("DJANGO_NUMBER", default_number)
dj_tag_start_end = Attribute("DJANGO_TAG_START_END", default_braces)
dj_filter = Attribute("DJANGO_FILTER", default_braces, scope='support.function')

# Gql
gql_string_literal = Attribute("GQL_STRING_LITERAL", default_string)
gql_keyword = Attribute("GQL_KEYWORD", default_keyword)
gql_int_literal = Attribute("GQL_INT_LITERAL", default_number)
gql_id =Attribute("GQL_ID", default_number)

# BuildoutCfgSyntaxHighlighter
bld_section_name = Attribute("BUILDOUT.SECTION_NAME", default_number)
bld_key = Attribute("BUILDOUT.KEY", default_keyword)
bld_value = Attribute("BUILDOUT.VALUE", default_string)
bld_comment = Attribute("BUILDOUT.LINE_COMMENT", default_line_comment)
bld_separator = Attribute("BUILDOUT.KEY_VALUE_SEPARATOR", default_operation_sign)

# REST
rest_line_comment = Attribute("REST.LINE_COMMENT", default_line_comment)
rest_section_header = Attribute("REST.SECTION.HEADER", default_number)
rest_bold = Attribute("REST.BOLD", text, font_style=1)
rest_italic = Attribute("REST.ITALIC", text, font_style=2)
rest_fixed = Attribute("REST.FIXED", text, background=(217, 217, 240))
rest_interpreted = Attribute("REST.INTERPRETED", text, background=(202, 218, 186))
rest_ref_name = Attribute("REST.REF.NAME", default_string)
rest_explicit = Attribute("REST.EXPLICIT", default_keyword)
rest_field = Attribute("REST.FIELD", default_keyword)
rest_inline = Attribute("REST.INLINE", text, background=(237, 252, 237))

# CSS
css_ident = Attribute("CSS.IDENT", html_tag_name, scope='entity.other.attribute-name.class.css')
css_comment = Attribute("CSS.COMMENT", html_comment, scope='comment.block.css')
css_property_name = Attribute("CSS.PROPERTY_NAME", html_attribute_name, scope='support.type.property-name')
css_property_value = Attribute("CSS.PROPERTY_VALUE", html_attribute_value, scope='meta.property-value.css')
css_tag_name = Attribute("CSS.TAG_NAME", html_tag_name, scope='entity.name.tag.css')
css_number = Attribute("CSS.NUMBER", default_number, scope='constant.numeric.css')
css_function = Attribute("CSS.FUNCTION", html_tag_name, scope='support.function.misc.css')
css_url = Attribute("CSS.URL", html_attribute_value, scope='variable.parameter.misc.css')

# LESS
less_variable = Attribute("LESS_VARIABLE", text, scope='variable.other.less')
less_code_injection_delim = Attribute("LESS_JS_CODE_DELIM", text, scope='source.css.less')
less_code_injection = Attribute("LESS_INJECTED_CODE", text, scope='source.js.embedded.less', foreground=IGNORE_COLOR)

# SASS
sass_identifier = Attribute("SASS_IDENTIFIER", css_ident, scope='entity.other.attribute-name.class.css')
sass_variable = Attribute("SASS_VARIABLE", text, scope='variable.parameter.sass')
sass_string = Attribute("SASS_STRING", default_string, scope='string.quoted.double.css')
sass_extend = Attribute("SASS_EXTEND", default_keyword, scope='keyword.control.at-rule.css')
sass_keyword = Attribute("SASS_KEYWORD", default_keyword, scope='keyword.control.at-rule.css')
sass_important = Attribute("SASS_IMPORTANT", default_keyword, scope='keyword.control.at-rule.css')
sass_default = Attribute("SASS_DEFAULT", default_keyword, scope='keyword.control.at-rule.css')
sass_property_name = Attribute("SASS_PROPERTY_NAME", css_property_name, scope='support.type.property-name.css')
sass_property_value = Attribute("SASS_PROPERTY_VALUE", css_property_value, scope='support.constant.property-value.css')
sass_tag_name = Attribute("SASS_TAG_NAME", css_tag_name, scope='meta.selector.css entity.name.tag')
sass_function = Attribute("SASS_FUNCTION", css_function, scope='support.constant.property-value.css')
sass_url = Attribute("SASS_URL", css_url, scope='support.constant.property-value.css')
sass_mixin = Attribute("SASS_MIXIN", default_keyword, scope='entity.other.attribute-name.tag')
sass_comment = Attribute("SASS_COMMENT", default_block_comment, scope='comment.block.css')
sass_number = Attribute("SASS_NUMBER", default_number, scope='constant.numeric.css')

# JS
js_regexp = Attribute("JS.REGEXP", default_string, scope='string.regexp')
js_local_var = Attribute("JS.LOCAL_VARIABLE", default_local_variable)
js_global_var = Attribute("JS.GLOBAL_VARIABLE", default_global_variable)
js_parameter = Attribute("JS.PARAMETER", default_parameter, effect_type=1, scope='variable.parameter')
js_instance_member_func = Attribute("JS.INSTANCE_MEMBER_FUNCTION", default_instance_method)

# YAML
yaml_comment = Attribute("YAML_COMMENT", default_line_comment, scope="comment.line.number-sign.yaml")
yaml_scalar_key = Attribute("YAML_SCALAR_KEY", default_keyword, scope="entity.name.tag.yaml")
yaml_scalar_value = Attribute("YAML_SCALAR_VALUE", text, scope="string.unquoted.block.yaml")
yaml_scalar_string = Attribute("YAML_SCALAR_STRING", text, scope="string.quoted.single.yaml")
yaml_scalar_dstring = Attribute("YAML_SCALAR_DSTRING", text, scope="string.quoted.double.yaml")
yaml_scalar_list = Attribute("YAML_SCALAR_LIST", text, scope="string.unquoted.block.yaml")
yaml_text = Attribute("YAML_TEXT", text, scope="string.unquoted.yaml")
yaml_sign = Attribute("YAML_SIGN", default_operation_sign)

# Puppet
puppet_comment = Attribute("PUPPET_BLOCK_COMMENT", default_line_comment, scope="comment.block.puppet")
puppet_regex = Attribute("PUPPET_REGEX", default_string, scope='string.regexp')
puppet_variable = Attribute("PUPPET_VARIABLE", default_local_variable, scope="punctuation.definition.variable.puppet")
puppet_variable_interpolation = Attribute("PUPPET_VARIABLE_INTERPOLATION", default_string, scope='string source')
puppet_escape_sequence = Attribute("PUPPET_ESCAPE_SEQUENCE", default_valid_string_escape)
puppet_resource_reference = Attribute("PUPPET_RESOURCE_REFERENCE", text)
puppet_keyword = Attribute("PUPPET_KEYWORD", default_keyword, scope="keyword.control.puppet")
puppet_digit = Attribute("PUPPET_NUMBER", default_number)
puppet_dq_string = Attribute("PUPPET_STRING", default_string, scope="string.quoted.double.puppet")
puppet_sq_string = Attribute("PUPPET_SQ_STRING", default_string, scope="string.quoted.single.puppet")
puppet_operation_sign = Attribute("PUPPET_OPERATION_SIGN", default_operation_sign, scope="keyword.operator.assignment.puppet")
puppet_parenths = Attribute("PUPPET_PARENTH", default_parentheses, scope="punctuation.section.scope.puppet")
puppet_brackets = Attribute("PUPPET_BRACKETS", default_brackets, scope="punctuation.definition.array.begin.puppet")
puppet_braces = Attribute("PUPPET_BRACES", default_braces, scope="punctuation.section.scope.puppet")
puppet_comma = Attribute("PUPPET_COMMA", default_comma)
puppet_dot = Attribute("PUPPET_DOT", default_dot)
puppet_semicolon = Attribute("PUPPET_SEMICOLON", default_semicolon)
puppet_bat_character = Attribute("PUPPET_BAD_CHARACTER", bad_character)
puppet_class = Attribute("PUPPET_CLASS", default_class_name, scope="entity.name.type.class.puppet")

# RubyHighlighter
rb_keyword = Attribute("RUBY_KEYWORD", default_keyword)
rb_comment = Attribute("RUBY_COMMENT", default_line_comment)
rb_heredoc_id = Attribute("RUBY_HEREDOC_ID", default_string, scope="punctuation.definition.string.begin.ruby")
rb_heredoc = Attribute("RUBY_HEREDOC_CONTENT", default_string, scope='string.unquoted.heredoc.ruby')
rb_number = Attribute("RUBY_NUMBER", default_number)
rb_string = Attribute("RUBY_STRING", default_string, scope="string.quoted.single.ruby")
rb_interpolated_string = Attribute("RUBY_INTERPOLATED_STRING", default_string, scope="string.quoted.double.ruby")
rb_words = Attribute("RUBY_WORDS", default_string, scope= "string.quoted.other.literal.upper.ruby")
rb_escape_sequence = Attribute("RUBY_ESCAPE_SEQUENCE", default_valid_string_escape)
rb_invalid_escape_sequence = Attribute("RUBY_INVALID_ESCAPE_SEQUENCE", default_invalid_string_escape)
rb_opSign = Attribute("RUBY_OPERATION_SIGN", default_operation_sign)
rb_brackets = Attribute("RUBY_BRACKETS", default_brackets)
rb_expr_in_string = Attribute("RUBY_EXPR_IN_STRING", default_string, scope='string source')
rb_bad_character = Attribute("RUBY_BAD_CHARACTER", text, scope='invalid')
rb_regexp = Attribute("RUBY_REGEXP", default_string, scope='string.regexp')
rb_identifier = Attribute("RUBY_IDENTIFIER", text, scope='variable')
rb_method_name = Attribute("RUBY_METHOD_NAME", rb_identifier, scope='entity.name.function')
rb_constant = Attribute("RUBY_CONSTANT", rb_identifier, scope='constant')
rb_constant_decl = Attribute("RUBY_CONSTANT_DECLARATION", rb_identifier, scope='entity.name.type.class.ruby')
rb_gvar = Attribute("RUBY_GVAR", rb_identifier, scope='variable.other.readwrite.global')
rb_cvar = Attribute("RUBY_CVAR", rb_identifier, scope='variable.other.readwrite.class')
rb_ivar = Attribute("RUBY_IVAR", rb_identifier, scope='variable.other.readwrite.instance')
rb_nth_ref = Attribute("RUBY_NTH_REF", text)
rb_comma = Attribute("RUBY_COMMA", default_comma, scope='punctuation.separator.object')
rb_dot = Attribute("RUBY_DOT", default_dot, scope='punctuation.separator.method')
rb_colon = Attribute("RUBY_COLON", default_semicolon)
rb_semicolon = Attribute("RUBY_SEMICOLON", default_semicolon, scope='punctuation.separator.statement')
rb_hash_assoc = Attribute("RUBY_HASH_ASSOC", default_operation_sign, scope='punctuation.separator.key-value')
rb_line_continuation = Attribute("RUBY_LINE_CONTINUATION", default_operation_sign)
rb_local_var = Attribute("RUBY_LOCAL_VAR_ID", rb_identifier)
rb_parameter = Attribute("RUBY_PARAMETER_ID", rb_identifier, scope='variable.parameter')
rb_symbol = Attribute("RUBY_SYMBOL", rb_identifier, scope='constant.other.symbol')
rb_specific_call = Attribute("RUBY_SPECIFIC_CALL", rb_identifier, scope='storage')
rb_paramdef = Attribute("RUBY_PARAMDEF_CALL", rb_identifier, scope='support.function')

# HAML
haml_text = Attribute("HAML_TEXT", text, scope='text.haml')
haml_class = Attribute("HAML_CLASS", haml_text, scope='entity.name.tag.class.haml')
haml_id = Attribute("HAML_ID", haml_text, scope='entity.name.tag.id.haml')
haml_tag = Attribute("HAML_TAG", haml_text, scope='punctuation.definition.tag.haml')
haml_tag_name = Attribute("HAML_TAG_NAME", haml_class, scope='meta.tag.haml')
haml_tag_attribute_name = Attribute("TAG_ATTR_KEY", haml_text, scope='entity.other.attribute-name.html')
haml_comment = Attribute("HAML_COMMENT", default_line_comment, scope='comment.line.slash.haml')
haml_xhtml = Attribute("HAML_XHTML", haml_text, scope='meta.prolog.haml')
haml_code_injection = Attribute("HAML_RUBY_CODE", haml_text, scope='source.ruby.embedded.haml', foreground=IGNORE_COLOR)
haml_ruby_evaluator = Attribute("HAML_RUBY_START", haml_text, scope='meta.line.ruby.haml')
haml_line_continuation = Attribute("HAML_LINE_CONTINUATION", haml_text)
haml_filter = Attribute("HAML_FILTER", haml_text)
haml_filter_content = Attribute("HAML_FILTER_CONTENT", haml_text)
haml_string = Attribute("HAML_STRING", default_string, scope="string.quoted.single.haml")
haml_string_interpolated = Attribute("HAML_STRING_INTERPOLATED", default_string, scope="string.quoted.double.haml")
haml_parenths = Attribute("HAML_PARENTHS", default_parentheses)
haml_ws_removal = Attribute("HAML_WS_REMOVAL", haml_text, scope='punctuation')

# SLIM
slim_text = Attribute("SLIM_STATIC_CONTENT", text, scope='text.slim')
slim_tag = Attribute("SLIM_TAG", slim_text, scope='entity.name.tag.slim')
slim_class = Attribute("SLIM_CLASS", slim_tag)
slim_id = Attribute("SLIM_ID", slim_tag)
slim_tag_start = Attribute("SLIM_TAG_START", slim_text, scope='punctuation.definition.tag.slim')
slim_tag_attribute_name = Attribute("SLIM_TAG_ATTR_KEY", haml_text, scope='entity.other.attribute-name.html')
slim_comment = Attribute("SLIM_COMMENT", default_line_comment, scope='comment.line.slash.slim')
slim_doctype = Attribute("SLIM_DOCTYPE_KWD", slim_tag, scope='meta.prolog.slim')
slim_code_injection = Attribute("SLIM_RUBY_CODE", haml_text, scope='source.ruby.embedded.slim', foreground=IGNORE_COLOR)
slim_call = Attribute("SLIM_CALL", slim_text, scope='meta.line.ruby.slim')
slim_interpolation = Attribute("SLIM_INTERPOLATION", rb_expr_in_string)
slim_bad_character = Attribute("SLIM_BAD_CHARACTER", slim_text, scope="invalid.illegal.bad-ampersand.html")
slim_parenths = Attribute("SLIM_PARENTHS", default_parentheses)
slim_filter = Attribute("SLIM_FILTER", slim_tag)
slim_filter_content = Attribute("SLIM_FILTER_CONTENT", slim_text)
slim_string_interpolated = Attribute("SLIM_STRING_INTERPOLATED", default_string, scope="string.quoted.double.html")

# Cucumber (Gherkin)
cucumber_text = Attribute("GHERKIN_TEXT", text, scope='text.gherkin.feature')
cucumber_comment = Attribute("GHERKIN_COMMENT", default_line_comment, scope='comment.line.number-sign')
cucumber_keyword = Attribute("GHERKIN_KEYWORD", default_keyword, scope='keyword.language.gherkin.feature')
cucumber_tag = Attribute("GHERKIN_TAG", cucumber_text, scope='storage.type.tag.cucumber')
cucumber_pystring = Attribute("GHERKIN_PYSTRING", default_string, scope='string.quoted.single')
cucumber_table_header = Attribute("GHERKIN_TABLE_HEADER_CELL", cucumber_text, scope='variable.other')
cucumber_table_cell = Attribute("GHERKIN_TABLE_CELL", cucumber_text)
cucumber_table_pipe = Attribute("GHERKIN_TABLE_PIPE", default_semicolon, scope='keyword.control.cucumber.table')
cucumber_outline_param_substitution = Attribute("GHERKIN_OUTLINE_PARAMETER_SUBSTITUTION", cucumber_text, scope='variable.other')
cucumber_scenario_regexp_param = Attribute("GHERKIN_REGEXP_PARAMETER", cucumber_text, scope='string.quoted.double')

#CoffeeScript
coffee_block_comment = Attribute("COFFEESCRIPT.BLOCK_COMMENT", default_block_comment, scope='comment.block.coffee')
coffee_line_comment = Attribute("COFFEESCRIPT.LINE_COMMENT", default_block_comment, scope='comment.line.coffee')
coffee_bad_char = Attribute("COFFEESCRIPT.BAD_CHARACTER", bad_character)
coffee_semicolon = Attribute("COFFEESCRIPT.SEMICOLON", default_semicolon, scope='punctuation.terminator.statement.coffee')
coffee_comma = Attribute("COFFEESCRIPT.COMMA", default_comma, scope='meta.delimiter.object.comma.coffee')
coffee_dot = Attribute("COFFEESCRIPT.DOT", default_dot, scope='meta.delimiter.method.period.coffee')
coffee_class = Attribute("COFFEESCRIPT.CLASS_NAME", text, scope='entity.name.function.coffee')
coffee_identifier = Attribute("COFFEESCRIPT.IDENTIFIER", text, scope='source.coffee', background=IGNORE_COLOR)
coffee_local_var = Attribute("COFFEESCRIPT.LOCAL_VARIABLE", coffee_identifier)
coffee_global_var = Attribute("COFFEESCRIPT.GLOBAL_VARIABLE", coffee_identifier, scope='variable.other.readwrite.global')
coffee_function_name = Attribute("COFFEESCRIPT.FUNCTION_NAME", text, scope='entity.name.function.coffee')
coffee_obj_key = Attribute("COFFEESCRIPT.OBJECT_KEY", text, scope='variable.assignment.coffee')
coffee_number = Attribute("COFFEESCRIPT.NUMBER", default_number, scope='constant.numeric.coffee')
coffee_bool = Attribute("COFFEESCRIPT.BOOLEAN", default_keyword, scope='constant.language.boolean')
coffee_str_bound = Attribute("COFFEESCRIPT.STRING_LITERAL", default_string, scope='punctuation.definition.string.begin.coffee')
coffee_str = Attribute("COFFEESCRIPT.STRING", default_string, scope='string.quoted.single.coffee')
coffee_heredoc_id = Attribute("COFFEESCRIPT.HEREDOC_ID", default_string, scope='punctuation.definition.string.begin.coffee')
coffee_heredoc_content = Attribute("COFFEESCRIPT.HEREDOC_CONTENT", default_string, scope='string.quoted.double.heredoc.coffee')
coffee_heregex_id = Attribute("COFFEESCRIPT.HEREGEX_ID", default_string, scope='string.regexp.coffee')
coffee_heregex_content = Attribute("COFFEESCRIPT.HEREGEX_CONTENT", default_string, scope='string.regexp.coffee')
coffee_js_id = Attribute("COFFEESCRIPT.JAVASCRIPT_ID", default_string, scope='punctuation.definition.string.begin.coffee')
coffee_expression_substitution = Attribute("COFFEESCRIPT.EXPRESSIONS_SUBSTITUTION_MARK", text, scope='punctuation.section.embedded.coffee')
coffee_parenths = Attribute("COFFEESCRIPT.PARENTHESIS", default_parentheses, scope='meta.brace.round.coffee')
coffee_brackets = Attribute("COFFEESCRIPT.BRACKET", default_brackets, scope='meta.brace.square.coffee')
coffee_braces = Attribute("COFFEESCRIPT.BRACE", default_braces, scope='meta.brace.curly.coffee')
coffee_operator = Attribute("COFFEESCRIPT.OPERATIONS", text, scope='keyword.operator.coffee')
coffee_operator_exists = Attribute("COFFEESCRIPT.EXISTENTIAL", text, scope='keyword.operator.coffee')
coffee_keyword = Attribute("COFFEESCRIPT.KEYWORD", default_keyword, scope='keyword.control.coffee')
coffee_range = Attribute("COFFEESCRIPT.RANGE", default_dot, scope='meta.delimiter.method.period.coffee')
coffee_splat = Attribute("COFFEESCRIPT.SPLAT", default_dot, scope='meta.delimiter.method.period.coffee')
coffee_this = Attribute("COFFEESCRIPT.THIS", default_keyword, scope='variable.language.coffee')
coffee_colon = Attribute("COFFEESCRIPT.COLON", default_semicolon, scope='keyword.operator.coffee')
coffee_prototype = Attribute("COFFEESCRIPT.PROTOTYPE", text, scope='entity.name.function.coffee')
coffee_fun_arrow = Attribute("COFFEESCRIPT.FUNCTION", default_number, scope='storage.type.function.coffee')
coffee_fun_binding_arrow = Attribute("COFFEESCRIPT.FUNCTION_BINDING", default_number, scope='storage.type.function.coffee')
coffee_regexp_id = Attribute("COFFEESCRIPT.REGULAR_EXPRESSION_ID", default_string, scope='string.regexp.coffee')
coffee_regexp = Attribute("COFFEESCRIPT.REGULAR_EXPRESSION_CONTENT", default_string, scope='string.regexp.coffee')
coffee_regexp_flag = Attribute("COFFEESCRIPT.REGULAR_EXPRESSION_FLAG", default_string, scope='string.regexp.coffee')
coffee_escaped_chars = Attribute("COFFEESCRIPT.ESCAPE_SEQUENCE", default_valid_string_escape, scope='constant.character.escape.coffe')
coffee_js_injection = Attribute("COFFEESCRIPT.JAVASCRIPT_CONTENT", default_string, scope='string.quoted.script.coffee', foreground=IGNORE_COLOR)


# ERB : "text.html.ruby"
erb_text = xml_tag
erb_block_start = Attribute("RHTML_SCRIPTLET_START_ID", erb_text, scope='punctuation.section.embedded.ruby')
erb_block_end = Attribute("RHTML_SCRIPTLET_END_ID", erb_text, scope='punctuation.section.embedded.ruby')
erb_block_expression_start = Attribute("RHTML_EXPRESSION_START_ID", erb_text, scope='punctuation.section.embedded.ruby')
erb_block_expression_end = Attribute("RHTML_EXPRESSION_END_ID", erb_text, scope='punctuation.section.embedded.ruby')
erb_comment = Attribute("RHTML_COMMENT_ID", default_line_comment, scope='comment.block.erb')
erb_omit_line_modifier = Attribute("RHTML_OMIT_NEW_LINE_ID", erb_text, scope='punctuation.section.embedded.ruby')
erb_ruby_injection_bg = Attribute("RHTML_SCRIPTING_BACKGROUND_ID", erb_text, scope='source.ruby.rails.embedded.html', foreground=IGNORE_COLOR)

# ClojureHighlighter
clj_comment = Attribute("Clojure Line comment", default_line_comment)
clj_atom = Attribute("Clojure Atom", default_keyword)
clj_keyword = Attribute("Clojure Keyword", rb_identifier)
clj_numbers = Attribute("Clojure Numbers", default_number)
clj_strings = Attribute("Clojure Strings", default_string)
clj_character = Attribute("Clojure Character", default_string)
clj_literal = Attribute("Clojure Literal", default_instance_field)
clj_first_in_list = Attribute("First symbol in list", rb_identifier, font_style=1)

# Objective-C Highlighter

oc_typedef = Attribute("TYPEDEF", text, 'storage.type')
oc_block_comment = Attribute("OC.BLOCK_COMMENT", default_block_comment)
oc_line_comment = Attribute("OC.LINE_COMMENT", default_line_comment)
oc_cpp_keyword = Attribute("OC.CPP_KEYWORD", default_keyword)
oc_conditionally_not_compiled = Attribute("CONDITIONALLY_NOT_COMPILED", default_block_comment)
oc_directive = Attribute("OC.DIRECTIVE", text, scope='keyword.other.directive')
oc_ivar = Attribute("IVAR", text, scope='variable.other.selector.objc')
oc_local_variable = Attribute("OC.LOCAL_VARIABLE", text, scope='variable.other.selector.objc')
oc_global_variable = Attribute("OC.GLOBAL_VARIABLE", oc_local_variable)
oc_extern_variable = Attribute("OC.EXTERN_VARIABLE", oc_local_variable)
oc_property = Attribute("OC.PROPERTY", oc_ivar)
oc_keyword = Attribute("OC.KEYWORD", default_keyword)
oc_label = Attribute("LABEL", oc_keyword)
oc_number = Attribute("OC.NUMBER", default_number)
oc_selfsuperthis = Attribute("OC.SELFSUPERTHIS", oc_keyword, scope='variable.language.objc')
oc_string = Attribute("OC.STRING", default_string)
oc_struct_field = Attribute("OC.STRUCT_FIELD", text, scope='constant.other.symbol')
oc_format_token = Attribute("OC_FORMAT_TOKEN", default_string, scope='string source')
oc_class_reference = Attribute("CLASS_REFERENCE", oc_typedef, scope='entity.name.class')
oc_protocol_reference = Attribute("PROTOCOL_REFERENCE", oc_class_reference, scope='meta.implementation.objc')
oc_message_argument = Attribute("OC.MESSAGE_ARGUMENT", default_function_call, scope='entity.name.function')
oc_method_declaration = Attribute("OC.METHOD_DECLARATION", default_function_declaration,  scope='entity.name.function')
oc_parameter = Attribute("OC.PARAMETER", text, scope='variable.parameter.function.objc')
oc_badcharacter = Attribute("OC.BADCHARACTER", text, scope='invalid')
oc_dot = Attribute("OC.DOT", text)
oc_comma = Attribute("OC.COMMA", oc_dot)
oc_braces = Attribute("OC.BRACES", oc_dot)
oc_brackets = Attribute("OC.BRACKETS", oc_dot)
oc_semicolon = Attribute("OC.SEMICOLON", oc_dot)
oc_operation_sign = Attribute("OC.OPERATION_SIGN", oc_dot)
oc_parenths = Attribute("OC.PARENTHS", oc_dot)
oc_enum_const = Attribute("ENUM_CONST", text, scope='constant.other.symbol')
oc_macroname = Attribute("MACRONAME", oc_message_argument)
oc_macro_parameter = Attribute("MACRO_PARAMETER", text)

# PHP
php_var = Attribute("PHP_VAR", default_local_variable)
php_parameter = Attribute("PHP_PARAMETER", default_parameter)

# Go
go_block_comment = Attribute("GO_BLOCK_COMMENT", default_block_comment)
go_line_comment = Attribute("GO_LINE_COMMENT", default_line_comment)
go_builtin_constant = Attribute("GO_BUILTIN_CONSTANT", default_constant)
go_local_constant = Attribute("GO_LOCAL_CONSTANT", default_constant)
go_package_local_constant = Attribute("GO_PACKAGE_LOCAL_CONSTANT", default_constant)
go_package_exported_constant = Attribute("GO_PACKAGE_EXPORTED_CONSTANT", default_constant)
go_builtin_variable = Attribute("GO_BUILTIN_VARIABLE", default_global_variable)
go_method_receiver = Attribute("GO_METHOD_RECEIVER", default_local_variable)
go_exported_function = Attribute("GO_EXPORTED_FUNCTION", default_function_declaration)
go_local_function = Attribute("GO_LOCAL_FUNCTION", default_function_declaration)
go_builtin_function_call = Attribute("GO_BUILTIN_FUNCTION_CALL", default_function_call)
go_local_function_call = Attribute("GO_LOCAL_FUNCTION_CALL", default_function_call)
go_exported_function_call = Attribute("GO_EXPORTED_FUNCTION_CALL", default_function_call)
go_keyword = Attribute("GO_KEYWORD", default_keyword)
go_package = Attribute("GO_PACKAGE", default_identifier)
go_builtin_type_reference = Attribute("GO_BUILTIN_TYPE_REFERENCE", default_class_name)
go_type_reference = Attribute("GO_TYPE_REFERENCE", default_class_name)

# CustomHighlighter
custom_number = Attribute("CUSTOM_NUMBER_ATTRIBUTES", default_number)
custom_string = Attribute("CUSTOM_STRING_ATTRIBUTES", default_string)
custom_line_comment = Attribute("CUSTOM_LINE_COMMENT_ATTRIBUTES", default_line_comment)
custom_multi_line_comment = Attribute("CUSTOM_MULTI_LINE_COMMENT_ATTRIBUTES", default_doc_comment)
custom_valid_string_escape = Attribute("CUSTOM_VALID_STRING_ESCAPE_ATTRIBUTES", default_valid_string_escape)
custom_invalid_string_escape = Attribute("CUSTOM_INVALID_STRING_ESCAPE_ATTRIBUTES", default_invalid_string_escape)

# Jade
jade_statements = Attribute("JADE_STATEMENTS", default_keyword)
jade_file_path = Attribute("JADE_FILE_PATH", default_string)
jade_filter_name = Attribute("JADE_FILTER_NAME", default_label)
jade_js_block = Attribute("JADE_JS_BLOCK", default_identifier)

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
    if len(rgba) == 3:
        r = rgba[0]
        g = rgba[1]
        b = rgba[2]
        return r + r + g + g + b + b
    return rgba[:6]

def font_style_from_textmate(style):
    result = 0
    if 'bold' in style: result += 1
    if 'italic' in style: result += 2
    return result

def attr_from_textmate(settings, old_value, background):
    result = AttributeValue()

    if ('foreground' in settings) and ((old_value == None) or (old_value.default_fore != IGNORE_COLOR_VALUE)):
        result.foreground = color_from_textmate(settings['foreground'])

    if ('background' in settings) and ((old_value == None) or (old_value.default_back != IGNORE_COLOR_VALUE)):
        result.background = color_from_textmate(settings['background'], background)

    if 'fontStyle' in settings:
        tm_font_style = settings['fontStyle']
        result.font_style = font_style_from_textmate(tm_font_style)
        if 'underline' in tm_font_style:
            result.effect_type = 1
    return result

def find_by_scope(settings, scope):
    # compound scope
    less_specific = None
    less_specific_weight = 0
    less_specific_selector_size = 0
    # simple scope (without whitespaces and '-')
    ss_less_specific = None
    ss_less_specific_weight = 0
    for setting in settings:
        scope_of_setting = setting.get('scope', None)
        if scope_of_setting is None:
            if scope is None: return setting
        else:
            if not isinstance(scope_of_setting, list):
                scopes_of_setting = scope_of_setting.split(",")
            else:
                scopes_of_setting = scope_of_setting

            for aScope in scopes_of_setting:
                aScope = aScope.strip()

                # ignore excludes in scopes selectors,
                # more accurate parsing/matching required!
                chain_without_excludes = aScope.split(' -')[0]
                aScope_selectors = chain_without_excludes.split(' ')

                # We need:
                # 1. "Match the element deepest down in the scope e.g. string wins over source.php when the scope is source.php string.quoted."
                # it is very simple implementation of above rule
                matchingScope = aScope_selectors[-1]
                if matchingScope is None:
                    continue

                # Consider scope size as scope size until first not excluded element
                aScopeSelectorSize = 0
                for i in range(0, len(aScope_selectors) - 1):
                    aScopeSelectorSize = len(aScope_selectors[i].strip())
                isSimpleScope = (aScopeSelectorSize == 0)

                if matchingScope == scope:
                    if isSimpleScope:
                      return setting
                    less_specific = setting
                    less_specific_weight = len(matchingScope)
                    less_specific_selector_size = aScopeSelectorSize
                if scope is not None and scope.startswith(matchingScope):
                    # We need:
                    # 2.  "Match most of the deepest element e.g. string.quoted wins over string."
                    # so let's consider matched symbols count as weight
                    new_match_weight = len(matchingScope)
                    weight = ss_less_specific_weight if isSimpleScope else less_specific_weight
                    if new_match_weight > weight:
                        if isSimpleScope:
                            ss_less_specific = setting
                            ss_less_specific_weight = new_match_weight
                        else:
                            less_specific = setting
                            less_specific_weight = new_match_weight
                            less_specific_selector_size = aScopeSelectorSize
                    else:
                        # if matched part is equal and scope isn't simple - let's choose the shortest scope
                        # in general case should work better, because some where particular complicated
                        # scope won't override similar but more general scope
                        if not isSimpleScope and (new_match_weight == weight):
                            if less_specific_selector_size > aScopeSelectorSize:
                                less_specific = setting
                                less_specific_weight = new_match_weight
                                less_specific_selector_size = aScopeSelectorSize

    return ss_less_specific if (ss_less_specific is not None) else less_specific

def load_textmate_scheme(tmtheme):
    themeDict = None
    with open(tmtheme, 'rb') as f:
        themeDict = plistlib.load(f)
    all_settings = themeDict['settings']
    used_scopes = set()
    default_settings = find_by_scope(all_settings, None)
    if not default_settings:
        print("Cannot find default settings")
        return
    default_settings = default_settings['settings']

    text.value = attr_from_textmate(default_settings, None, None)

    background = None
    selection_background = None
    caret_row_color = None

    if 'background' in default_settings:
        background = default_settings['background']
        all_colors["GUTTER_BACKGROUND"] = color_from_textmate(background)

        if 'invisibles' in default_settings:
            all_colors['INDENT_GUIDE'] = color_from_textmate(default_settings['invisibles'], background)
            all_colors['SELECTED_INDENT_GUIDE'] = all_colors['INDENT_GUIDE']
            all_colors['WHITESPACES'] = color_from_textmate(default_settings['invisibles'], background)

        if 'selection' in default_settings:
            selection_background = color_from_textmate(default_settings['selection'], background)
            all_colors['SELECTION_BACKGROUND'] = selection_background

        if 'lineHighlight' in default_settings:
            caret_row_color = color_from_textmate(default_settings['lineHighlight'], background)

    if 'caret' in default_settings:
        all_colors['CARET_COLOR'] = color_from_textmate(default_settings['caret'])

    if 'foreground' in default_settings:
        all_colors["LINE_NUMBERS_COLOR"] = color_from_textmate(default_settings['foreground'])

    if caret_row_color is not None and selection_background is not None and selection_background == caret_row_color:
        y, i, q = hex_to_yiq(caret_row_color)
        if y < 0.5:
            y /= 2
        else:
            y += 0.2
        caret_row_color = rgb_to_hex(*colorsys.yiq_to_rgb(y, i, q))

    if caret_row_color is not None:
        all_colors['CARET_ROW_COLOR'] = caret_row_color

    all_colors['CONSOLE_BACKGROUND_KEY'] = text.value.background

    if background is not None:
        blend_spy_js_attributes(background)

    for attr in all_attributes:
        if attr.scope:
            settings = find_by_scope(all_settings, attr.scope)
            if settings:
                the_scope = settings['scope']
                if the_scope:
                    print("converting attribute " + attr.id + " from TextMate scope " + the_scope)
                    used_scopes.add(the_scope)
                attr.value = attr_from_textmate(settings['settings'], attr.value, background)
            else:
               print("[!] scope not found: " + attr.scope)
    return all_settings, used_scopes

def blend_spy_js_attributes(background):
    Attribute("SPY-JS.FUNCTION_SCOPE", text, background=blend_with_as_rgb256(background, "#FFFFF0", "04"), effect_type=2)
    Attribute("SPY-JS.PROGRAM_SCOPE", text, background=blend_with_as_rgb256(background, "#FFFFFF", "04"), effect_type=2)
    Attribute("SPY-JS.EXCEPTION", text, background=blend_with_as_rgb256(background, "#FFCCCC", "04"), effect_type=2)
    Attribute("SPY-JS.PATH_LEVEL_ONE", text, background=blend_with_as_rgb256(background, "#E2FFE2", "04"), effect_type=2)
    Attribute("SPY-JS.PATH_LEVEL_TWO", text, effect_type=1)
    Attribute("SPY-JS.VALUE_HINT", text, effect_type=0)
    return

def blend_with_as_rgb256(base_hex_color, blend_with_hex_color, blend_hex_alpha):
    result = hex_to_rgb(color_from_textmate(base_hex_color + blend_hex_alpha, blend_with_hex_color))
    return int(result[0] * 256), int(result[1] * 256), int(result[2] * 256)

def underscore_to_camelcase(value):
    def camelcase():
        while True:
            yield str.capitalize

    c = camelcase()
    return "".join(next(c)(x) if x else '_' for x in value.split("_"))

def isDark():
    back = hex_to_rgb(text.value.background)
    intensity = (back[0] + back[1] + back[2])/3
    return intensity < 0.5

def removeNoneAttrib(elem):
    """Remove None attributes from XML tree"""
    elem.attrib = {
        k: elem.attrib[k]
        for k in elem.attrib
        if elem.attrib[k] is not None
    }
    for subelem in elem:
        removeNoneAttrib(subelem)

def write_idea_scheme(filename):
    name, ext = os.path.splitext(os.path.basename(filename))
    baseName = "Darcula" if isDark() else "Default"
    scheme = ET.Element("scheme", name=underscore_to_camelcase(name), version="1", parent_scheme=baseName)
    colors = ET.SubElement(scheme, 'colors')
    for name, value in all_colors.items():
        ET.SubElement(colors, 'option', name=name, value=value)
    attributes = ET.SubElement(scheme, 'attributes')

    # let's sort attributes, then diffs between generated schemes will look nice
    all_attributes.sort(key=lambda attr: attr.id)

    for attr in all_attributes:
        if attr.value.inherited:
            print('inheriting ' + attr.id + ' from ' + attr.parent.id)
        elif isinstance(attr.value, DerivedAttributeValue):
            print('transforming IDEA default color for ' + attr.id)
        fore = attr.value.foreground
        back = attr.value.background
        saveFg = fore and (fore != IGNORE_COLOR_VALUE)
        saveBg = back and (back != IGNORE_COLOR_VALUE)
        if saveFg or saveBg or attr.value.font_style or attr.value.effect_type or attr.value.error_stripe:
            option = ET.SubElement(attributes, 'option', name=attr.id)
            value = ET.SubElement(option, 'value')
            if saveFg: ET.SubElement(value, 'option', name='FOREGROUND', value=fore)
            if saveBg: ET.SubElement(value, 'option', name='BACKGROUND', value=back)
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
        else:
            ET.SubElement(attributes, 'option', name=attr.id, baseAttributes=attr.parent.id)
    indent(scheme)
    capitalize_colors(scheme)
    tree = ET.ElementTree(scheme)
    removeNoneAttrib(tree.getroot())
    tree.write(filename)

if len(sys.argv) != 3:
    print('Usage: colorSchemeTool <TextMate scheme> <IDEA/PyCharm/RubyMine scheme>')
    exit(1)

all_settings, used_scopes = load_textmate_scheme(sys.argv[1])
write_idea_scheme(sys.argv[2])

for setting in all_settings:
    scope = setting.get('scope', None)
    if scope and not scope in used_scopes:
        print("Unused scope: " + scope)

