#!/usr/bin/python3
"""Tests for the templateparser module."""

# Too many public methods
# pylint: disable=R0904

# Standard modules
import os
import re
import time
import unittest

# Unittest target
from uweb3 import templateparser

class Parser(unittest.TestCase):
  """Basic tests for the Parser class and equality of Template objects."""
  def setUp(self):
    """Creates a template file and a similar instance attribute."""
    self.name = 'tmp_template'
    self.raw = 'This is a basic [noun]'
    self.template = templateparser.Template(self.raw)
    with open(self.name, 'w') as template:
      template.write('This is a basic [noun]')
      template.flush()

  def tearDown(self):
    """Removes the template file from the filesystem."""
    os.unlink('tmp_template')

  def testAddTemplate(self):
    """[Parser] AddTemplate adds a template to the parser"""
    parser = templateparser.Parser()
    self.assertEqual(len(parser), 0)
    parser.AddTemplate(self.name)
    self.assertEqual(len(parser), 1)
    self.assertEqual(parser[self.name], self.template)

  def testAccessTemplate(self):
    """[Parser] getting a template by key loads it when required"""
    parser = templateparser.Parser()
    self.assertEqual(len(parser), 0)
    self.assertEqual(parser[self.name], self.template)
    self.assertEqual(len(parser), 1)

  def testOverWriteTemplate(self):
    """[Parser] AddTemplate overrides previously loaded template"""
    custom_raw = 'My very own [adj] template'
    custom_tmpl = templateparser.Template(custom_raw)
    parser = templateparser.Parser()
    parser.AddTemplate(self.name)
    # Create a new template in place of the existing one, and reload it.
    with open(self.name, 'w') as tmpl:
      tmpl.write(custom_raw)
      tmpl.flush()
    # Assert the template has not yet changed, load it, assert that is has.
    self.assertNotEqual(custom_tmpl, parser[self.name])
    parser.AddTemplate(self.name)
    self.assertEqual(parser[self.name], custom_tmpl)

  def testPreloadTemplates(self):
    """[Parser] Templates can be preloaded when instantiating the Parser"""
    parser = templateparser.Parser(templates=[self.name])
    self.assertEqual(len(parser), 1)
    self.assertEqual(parser[self.name], self.template)

  def testParseVersusParseString(self):
    """[Parser] Parse and ParseString only differ in cached lookup"""
    parser = templateparser.Parser()
    result_parse = parser[self.name].Parse()
    result_parse_string = parser.ParseString(self.raw)
    self.assertEqual(result_parse, result_parse_string)


class ParserPerformance(unittest.TestCase):
  """Basic performance test of the Template's initialization and Parsing."""
  @staticmethod
  def testPerformance():
    """[Parser] Basic performance test for 2 template replacements"""
    template = 'This [obj:foo] is just a quick [bar]'
    for _template in range(100):
      tmpl = templateparser.Template(template)
      for _parse in range(100):
        tmpl.Parse(obj={'foo': 'template'}, bar='hack')


class TemplateTagBasic(unittest.TestCase):
  """Tests validity and parsing of simple tags."""
  def setUp(self):
    """Makes the Template class available on the instance."""
    self.tmpl = templateparser.Template

  def testTaglessTemplate(self):
    """[BasicTag] Templates without tags get returned verbatim as SafeString"""
    template = 'Template without any tags'
    self.assertEqual(self.tmpl(template).Parse(), template)

  def testSafeString(self):
    """[BasicTag] Templates without tags get returned verbatim as SafeString"""
    template = 'Template without any tags'
    parsed_template = self.tmpl(template).Parse()
    self.assertTrue(isinstance(parsed_template, templateparser.HTMLsafestring))

  def testSingleTagTemplate(self):
    """[BasicTag] Templates with basic tags get returned proper"""
    template = 'Template with [single] tag'
    result = self.tmpl(template).Parse(single='just one')
    self.assertEqual(result, 'Template with just one tag')

  def testSaveTagTemplate(self):
    """[BasicTag] Templates with basic tags get returned properly when replacement is already html safe"""
    template = 'Template with just [single] tag'
    result = self.tmpl(template).Parse(single=templateparser.HTMLsafestring('<b>a safe</b>'))
    self.assertEqual(result, 'Template with just <b>a safe</b> tag')

  def testUnsaveTagTemplate(self):
    """[BasicTag] Templates with basic tags get returned properly when replacement is not html safe"""
    template = 'Template with just [single] tag'
    result = self.tmpl(template).Parse(single='<b>an unsafe</b>')
    self.assertEqual(result, 'Template with just &lt;b&gt;an unsafe&lt;/b&gt; tag')

  def testCasedTag(self):
    """[BasicTag] Tag names are case-sensitive"""
    template = 'The parser has no trouble with [cAsE] [case].'
    result = self.tmpl(template).Parse(cAsE='mixed')
    self.assertEqual(result, 'The parser has no trouble with mixed [case].')

  def testUnderscoredTag(self):
    """[BasicTag] Tag names may contain underscores"""
    template = 'The template may contain [under_scored] tags.'
    result = self.tmpl(template).Parse(under_scored='underscored')
    self.assertEqual(result, 'The template may contain underscored tags.')

  def testMultiTagTemplate(self):
    """[BasicTag] Multiple instances of a tag will all be replaced"""
    template = '[adjective] [noun] are better than other [noun].'
    result = self.tmpl(template).Parse(noun='cows', adjective='Beefy')
    self.assertEqual(result, 'Beefy cows are better than other cows.')

  def testEmptyOrWhitespace(self):
    """[BasicTag] Empty tags or tags containing whitespace aren't actual tags"""
    template = 'This [is a] broken [] template, really'
    result = self.tmpl(template).Parse(**{'is a': 'HORRIBLY', '': ', NASTY'})
    self.assertEqual(result, template)

  def testBadCharacterTags(self):
    """[BasicTag] Tags containing bad characters are not considered tags"""
    bad_chars = """ :~!@#$%^&*()+-={}\|;':",./<>? """
    template = ''.join('[%s] [check]' % char for char in bad_chars)
    expected = ''.join('[%s] ..' % char for char in bad_chars)
    replaces = {char: 'FAIL' for char in bad_chars}
    replaces['check'] = '..'
    self.assertEqual(self.tmpl(template).Parse(**replaces), expected)

  def testUnreplacedTag(self):
    """[BasicTag] Template tags without replacement are returned verbatim"""
    template = 'Template with an [undefined] tag.'
    self.assertEqual(self.tmpl(template).Parse(), template)

  def testUnreplacedTag(self):
    """[BasicTag] Access to private members is not allowed"""
    template = 'Template with an [private.__class__] tag.'
    self.assertEqual(self.tmpl(template).Parse(), template)

  def testBracketsInsideTag(self):
    """[BasicTag] Innermost bracket pair are the tag's delimiters"""
    template = 'Template tags may not contain [[spam][eggs]].'
    expected = 'Template tags may not contain [opening or closing brackets].'
    result = self.tmpl(template).Parse(
        **{'[spam': 'EPIC', 'eggs]': 'FAIL', 'spam][eggs': 'EPIC FAIL',
           'spam': 'opening or ', 'eggs': 'closing brackets'})
    self.assertEqual(result, expected)

  def testTemplateInterpolationSyntax(self):
    """[BasicTag] Templates support string interpolation of dicts"""
    template = 'Hello [name]'
    self.assertEqual(self.tmpl(template) % {'name': 'Bob'}, 'Hello Bob')


class TemplateTagIndexed(unittest.TestCase):
  """Tests the handling of complex tags (those with attributes/keys/indexes)."""
  def setUp(self):
    """Sets up a parser instance, as it never changes."""
    self.tmpl = templateparser.Template

  def testTemplateMappingKey(self):
    """[IndexedTag] Template tags can address mappings properly"""
    template = 'This uses a [dictionary:key].'
    result = self.tmpl(template).Parse(dictionary={'key': 'spoon'})
    self.assertEqual(result, 'This uses a spoon.')

  def testTemplateIndexing(self):
    """[IndexedTag] Template tags can access indexed iterables"""
    template = 'Template that grabs the [obj:2] key from the given tuple/list.'
    expected = 'Template that grabs the third key from the given tuple/list.'
    numbers = 'first', 'second', 'third'
    self.assertEqual(self.tmpl(template).Parse(obj=numbers), expected)
    self.assertEqual(self.tmpl(template).Parse(obj=list(numbers)), expected)

  def testTemplateAttributes(self):
    """[IndexedTag] Template tags will do attribute lookups after key-lookups"""
    class Mapping(dict):
      """A subclass of a dictionary, so we can define attributes on it."""
      NAME = 'attribute'

    template = 'Template used [tag:NAME] lookup.'
    lookup_attr = 'Template used attribute lookup.'
    lookup_dict = 'Template used key (mapping) lookup.'

    mapp = Mapping()
    self.assertEqual(self.tmpl(template).Parse(tag=mapp), lookup_attr)
    mapp['NAME'] = 'key (mapping)'
    self.assertEqual(self.tmpl(template).Parse(tag=mapp), lookup_dict)

  def testTemplateIndexingCharacters(self):
    """[IndexedTag] Tags indexes may be made of word chars and dashes only,
    they should however not start and end with _ to avoid access to
    private vars.
    _ is allowed elsewhere in the string."""
    good_chars = "aAzZ0123-."
    bad_chars = """ :~!@#$%^&*()+={}\|;':",/<>? """
    for index in good_chars:
      tag = {index: 'SUCCESS'}
      template = '[tag:%s]' % index
      self.assertEqual(self.tmpl(template).Parse(tag=tag), 'SUCCESS')
    for index in bad_chars:
      tag = {index: 'FAIL'}
      template = '[tag:%s]' % index
      self.assertEqual(self.tmpl(template).Parse(tag=tag), template)

  def testTemplateUnderscoreCharacters(self):
    """[IndexedTag] Tags indexes may be made of word chars and dashes and dots
    only, they should however not start and end with _ to avoid access to
    private vars.
    _ is allowed elsewhere in the string."""
    # see if objects with underscores are reachable
    tag = {'test_test': 'SUCCESS'}
    template = '[tag:%s]' % 'test_test'
    self.assertEqual(self.tmpl(template).Parse(tag=tag), 'SUCCESS')

    tag = {'_test': 'SUCCESS'}
    template = '[tag:%s]' % '_test'
    self.assertEqual(self.tmpl(template).Parse(tag=tag), 'SUCCESS')

    tag = {'test_': 'SUCCESS'}
    template = '[tag:%s]' % 'test_'
    self.assertEqual(self.tmpl(template).Parse(tag=tag), 'SUCCESS')

    # check if private vars are impossible to reach.
    tag = {'_test_': 'SUCCESS'}
    template = '[tag:%s|raw]' % '_test_'
    self.assertEqual(self.tmpl(template).Parse(tag=tag), repr(tag))

  def testTemplateMissingIndexes(self):
    """[IndexedTag] Tags with bad indexes will be returned verbatim"""
    class Object:
      """A simple object to store an attribute on."""
      NAME = 'Freeman'

    template = 'Hello [titles:1] [names:NAME], how is [names:other] [date:now]?'
    expected = 'Hello [titles:1] Freeman, how is [names:other] [date:now]?'
    result = self.tmpl(template).Parse(titles=['Mr'], names=Object(), date={})
    self.assertEqual(result, expected)

  def testTemplateMultipleIndexing(self):
    """[IndexedTag] Template tags can contain multiple nested indexes"""
    template = 'Welcome to the [foo:bar:zoink].'
    result = self.tmpl(template).Parse(foo={'bar': {'zoink': 'World'}})
    self.assertEqual(result, 'Welcome to the World.')


class TemplateTagFunctions(unittest.TestCase):
  """Tests the functions that are performed on replaced tags."""
  def setUp(self):
    """Sets up a parser instance, as it never changes."""
    self.parser = templateparser.Parser()
    self.parse = self.parser.ParseString

  def testBasicFunction(self):
    """[TagFunctions] and html safe output"""
    template = 'This function does [none].'
    result = self.parse(template, none='"nothing"')
    self.assertEqual(result, 'This function does &quot;nothing&quot;.')

  def testBasicFunctionNumeric(self):
    """[TagFunctions] and html safe output for non string outputs"""
    template = '[tag]'
    result = self.parse(template, tag=1)
    self.assertEqual(result, '1')

  def testBasicFunctionRaw(self):
    """[TagFunctions] Raw function does not affect output"""
    template = 'This function does [none|raw].'
    result = self.parse(template, none='"nothing"')
    self.assertEqual(result, 'This function does "nothing".')

  def testNonexistantFuntion(self):
    """[TagFunctions] An error is raised for functions that don't exist"""
    template = 'This tag function is missing [num|zoink].'
    self.assertEqual(self.parse(template), template)
    # Error is only thrown if we actually pass an argument for the tag:
    self.assertRaises(templateparser.TemplateFunctionError,
                      self.parse, template, num=1)

  def testAlwaysString(self):
    """[TagFunctions] Tag function return is always converted to string."""
    template = '[number]'
    self.assertEqual(self.parse(template, number=1), '1')
    template = '[number|raw]'
    self.assertEqual(self.parse(template, number=2), '2')
    template = '[number|int]'
    self.parser.RegisterFunction('int', int)
    self.assertEqual(self.parse(template, number=3), '3')

  def testFunctionCharacters(self):
    """[TagFunctions] Tags functions may contain word chars and dashes only"""
    good_funcs = "aAzZ0123-_"
    good_func = lambda tag: 'SUCCESS'
    bad_funcs = """ :~!@#$%^&*+={}\;':"./<>?| """
    bad_func = lambda tag: 'FAIL'
    for index in good_funcs:
      template = '[tag|%s]' % index
      self.parser.RegisterFunction(index, good_func)
      self.assertEqual(self.parse(template, tag='foo'), 'SUCCESS')
    for index in bad_funcs:
      template = '[tag|%s]' % index
      self.parser.RegisterFunction(index, bad_func)
      self.assertEqual(self.parse(template, tag='foo'), template)
    self.parser.RegisterFunction('|', bad_func)

  def testDefaultHtmlSafe(self):
    """[TagFunctions] The default function escapes HTML entities"""
    default = 'This function does [none].'
    escaped = 'This function does [none|html].'
    expected = 'This function does &quot;nothing&quot;.'
    self.assertEqual(self.parse(default, none='"nothing"'), expected)
    self.assertEqual(self.parse(escaped, none='"nothing"'), expected)

  def testNoDefaultForSafeString(self):
    """[TagFunctions] The default function does not act upon SafeString parts"""
    first_template = 'Hello doctor [name]'
    second_template = '<assistant> [quote].'
    result = '<assistant> Hello doctor &quot;Who&quot;.'
    result_first = self.parse(first_template, name='"Who"')
    result_second = self.parse(second_template, quote=result_first)
    self.assertEqual(result, result_second)

  def testCustomFunction(self):
    """[TagFunctions] Custom functions can be added to the Parser"""
    self.parser.RegisterFunction('twice', lambda x: x + ' ' + x)
    template = 'The following will be stated [again|twice].'
    result = 'The following will be stated twice twice.'
    self.assertEqual(result, self.parse(template, again='twice'))

  def testFunctionChaining(self):
    """[TagFunctions] Multiple functions can be chained after one another"""
    self.parser.RegisterFunction('count', lambda x: '%s characters' % x)
    template = 'A replacement processed by two functions: [spam|len|count].'
    result = 'A replacement processed by two functions: 8 characters.'
    self.assertEqual(result, self.parse(template, spam='ham&eggs'))

  def testFunctionUse(self):
    """[TagFunctions] Tag functions are only called when requested by tags"""
    fragments_received = []
    def CountAndReturn(fragment):
      """Returns the given fragment after adding it to a counter list."""
      fragments_received.append(fragment)
      return fragment

    self.parser.RegisterFunction('count', CountAndReturn)
    template = 'Count only has [num|count] call, or it is [noun|raw].'
    result = self.parse(template, num='one', noun='broken')
    self.assertEqual(result, 'Count only has one call, or it is broken.')
    self.assertEqual(len(fragments_received), 1)

  def testTagFunctionUrl(self):
    """[TagFunctions] The tag function 'url' is present and works"""
    template = 'http://example.com/?breakfast=[query|url]'
    result = self.parse(template, query='"ham & eggs"')
    self.assertEqual(result, 'http://example.com/?breakfast=%22ham+%26+eggs%22')

  def testTagFunctionItems(self):
    """[TagFunctions] The tag function 'items' is present and works"""
    template = '[tag|items|raw]'
    tag = {'ham': 'eggs'}
    result = "[('ham', 'eggs')]"
    self.assertEqual(result, self.parse(template, tag=tag))

  def testTagFunctionValues(self):
    """[TagFunctions] The tag function 'values' is present and works"""
    template = '[tag|values|raw]'
    self.assertEqual(self.parse(template, tag={'ham': 'eggs'}), "['eggs']")

  def testTagFunctionSorted(self):
    """[TagFunctions] The tag function 'sorted' is present and works"""
    template = '[numbers|sorted]'
    numbers = [5, 1, 3, 2, 4]
    self.assertEqual(self.parse(template, numbers=numbers), "[1, 2, 3, 4, 5]")

  def testTagFunctionLen(self):
    """[TagFunctions] The tag function 'len' is present and works"""
    template = '[numbers|len]'
    self.assertEqual(self.parse(template, numbers=range(12)), "12")


class TemplateTagFunctionClosures(unittest.TestCase):
  """Tests the functions that are performed on replaced tags."""
  @staticmethod
  def Limit(length=80):
    """Returns a closure that limits input to a number of chars/elements."""
    return lambda string: string[:length]

  @staticmethod
  def LimitString(length=80, endchar='...'):
    """Limits input to `length` chars and appends `endchar` if it was longer."""
    def _Limit(string, length=length, endchar=endchar):
      if len(string) > length:
        return string[:length] + endchar
      return string
    return _Limit

  def setUp(self):
    """Sets up a parser instance, as it never changes."""
    self.parser = templateparser.Parser()
    self.parser.RegisterFunction('limit', self.Limit)
    self.parser.RegisterFunction('strlimit', self.LimitString)
    self.parse = self.parser.ParseString
    self.tag = 'hello world ' * 10

  def testSimpleClosureWithoutArguments(self):
    """[TagClosures] Simple tag closure-functions without arguments succeed"""
    template = '[tag|limit()]'
    result = self.parse(template, tag=self.tag)
    self.assertEqual(result, self.tag[:80])

  def testSimpleClosureArgument(self):
    """[TagClosures] Simple tag-closure functions operate on their argument"""
    template = '[tag|limit(20)]'
    result = self.parse(template, tag=self.tag)
    self.assertEqual(result, self.tag[:20])

  def testMathClosureArgument(self):
    """[TagClosures] Math tag-closure functions operate on their argument"""
    template = '[tag|limit(5*4)]'
    result = self.parse(template, tag=self.tag)
    self.assertEqual(result, self.tag[:20])

  def testFunctionClosureArgument(self):
    """[TagClosures] tags that use function calls in their function input should
    never be parsed"""
    template = '[tag|limit(abs(-20))]'
    result = self.parse(template, tag=self.tag)
    self.assertEqual(result, template)

  def testVariableClosureArgument(self):
    """[TagClosures] tags that try to use vars in their function arguments
    should never have access to the python scope."""
    test = 20
    template = '[tag|limit(test)]'
    self.assertRaises(templateparser.TemplateNameError,
        self.parse, template, tag=self.tag)

  def testComplexClosureWithoutArguments(self):
    """[TagClosures] Complex tag closure-functions without arguments succeed"""
    template = '[tag|strlimit()]'
    result = self.parse(template, tag=self.tag)
    self.assertEqual(len(result), 83)
    self.assertEqual(result[:80], self.tag[:80])
    self.assertEqual(result[-3:], '...')

  def testComplexClosureArguments(self):
    """[TagClosures] Complex tag closure-functions operate on arguments"""
    template = '[tag|strlimit(20, "TOOLONG")]'
    result = self.parse(template, tag=self.tag)
    self.assertEqual(len(result), 27)
    self.assertEqual(result[:20], self.tag[:20])
    self.assertEqual(result[-7:], 'TOOLONG')

  def testCharactersInClosureArguments(self):
    """[TagClosures] Arguments strings may contain specialchars"""
    template = '[tag|strlimit(20, "`-=./<>?`!@#$%^&*_+[]\{}|;\':")|raw]'
    result = self.parser.ParseString(template, tag=self.tag)
    self.assertTrue(result.endswith('`-=./<>?`!@#$%^&*_+[]\{}|;\':'))

  def testCommaInArgument(self):
    """[TagClosures] String arguments may contain commas"""
    template = '[tag|strlimit(10, "ham, eggs")]'
    result = self.parse(template, tag=self.tag)
    self.assertEqual(result[-9:], "ham, eggs")

  def testNamedArguments(self):
    """[TagClosures] Named arguments are not allowed"""
    template = '[tag|limit(length=20)]'
    self.assertRaises(templateparser.TemplateSyntaxError,
                      self.parse, template, tag=self.tag)

  def testTrailingComma(self):
    """[TagClosures] Arguments may not have a trailing comma"""
    template = '[tag|limit(20,)]'
    self.assertRaises(templateparser.TemplateSyntaxError,
                      self.parse, template, tag=self.tag)


class TemplateUnicodeSupport(unittest.TestCase):
  """TemplateParser handles Unicode gracefully."""
  def setUp(self):
    """Sets up a parser instance, as it never changes."""
    self.parser = templateparser.Parser()
    self.parse = self.parser.ParseString

  def testTemplateUnicode(self):
    """[Unicode] Templates may contain raw Unicode codepoints"""
    # And they will be converted to UTF8 eventually
    template = u'We \u2665 Python'
    self.assertEqual(self.parse(template), template)

  def testTemplateUTF8(self):
    """[Unicode] Templates may contain UTF8 encoded text"""
    # That is, input bytes will be left untouched
    template = u'We \u2665 Python'
    self.assertEqual(self.parse(template), template)

  def testUnicodeReplacements(self):
    """[Unicode] Unicode in tag replacements is converted to UTF8"""
    template = 'Underdark Web framework, also known as [name].'
    expected = u'Underdark Web framework, also known as \xb5Web.'
    self.assertEqual(self.parse(template, name=u'\xb5Web'), expected)

  def testUnicodeTagFunction(self):
    """[Unicode] Template functions returning unicode are converted to UTF8"""
    function_result = u'No more \N{BLACK HEART SUIT}'
    def StaticReturn(_fragment):
      """Returns a static string, for any input fragment."""
      return function_result

    self.parser.RegisterFunction('nolove', StaticReturn)
    template = '[love|nolove]'
    expected = function_result
    self.assertEqual(self.parse(template, love='love'), expected)

  def testTemplateTagUTF8(self):
    """[Unicode] Template tags may contain UTF8"""
    template = u'We \u2665 \xb5Web!'
    self.assertEqual(self.parse(template), template)


class TemplateInlining(unittest.TestCase):
  """TemplateParser properly handles the include statement."""
  def setUp(self):
    """Sets up a testbed."""
    self.parser = templateparser.Parser()
    self.parse = self.parser.ParseString
    self.tmpl = templateparser.Template

  def testInlineExisting(self):
    """{{ inline }} Parser will inline an already existing template reference"""
    self.parser['template'] = self.tmpl('This is a subtemplate by [name].')
    template = '{{ inline template }}'
    expected = 'This is a subtemplate by Elmer.'
    self.assertEqual(self.parse(template, name='Elmer'), expected)

  def testInlineFile(self):
    """{{ inline }} Parser will load an inlined template from file if needed"""
    with open('tmp_template', 'w') as inline_file:
      inline_file.write('This is a subtemplate by [name].')
      inline_file.flush()
    try:
      template = '{{ inline tmp_template }}'
      expected = 'This is a subtemplate by Elmer.'
      self.assertEqual(self.parse(template, name='Elmer'), expected)
    finally:
      os.unlink('tmp_template')


class TemplateConditionals(unittest.TestCase):
  """TemplateParser properly handles if/elif/else statements."""
  def setUp(self):
    """Sets up a testbed."""
    self.parse = templateparser.Parser().ParseString

  def testBasicConditional(self):
    """{{ if }} Basic boolean check works for relevant data types"""
    template = '{{ if [variable] }} ack {{ endif }}'
    # Boolean True inputs should return a SafeString object stating 'foo'.
    self.assertEqual(self.parse(template, variable=True), ' ack ')
    self.assertEqual(self.parse(template, variable='truth'), ' ack ')
    self.assertEqual(self.parse(template, variable=12), ' ack ')
    self.assertEqual(self.parse(template, variable=[1, 2]), ' ack ')
    # Boolean False inputs should yield an empty SafeString object.
    self.assertFalse(self.parse(template, variable=None))
    self.assertFalse(self.parse(template, variable=0))
    self.assertFalse(self.parse(template, variable=''))

  def testCompareTag(self):
    """{{ if }} Basic tag value comparison"""
    template = '{{ if [variable] == 5 }} foo {{ endif }}'
    self.assertFalse(self.parse(template, variable=0))
    self.assertFalse(self.parse(template, variable=12))
    self.assertTrue(self.parse(template, variable=5))

  def testCompareMath(self):
    """{{ if }} Basic math"""
    template = '{{ if 5*5 == 25 }} foo {{ endif }}'
    self.assertEqual(self.parse(template, variable=5).strip(), 'foo')

  def testTagIsInstance(self):
    """{{ if }} Tag value after python function comparison"""
    template = '{{ if isinstance([variable], int) }} ack {{ endif }}'
    self.assertFalse(self.parse(template, variable=[1]))
    self.assertFalse(self.parse(template, variable='number'))
    self.assertEqual(self.parse(template, variable=5), ' ack ')

  def testComparePythonFunction(self):
    """{{ if }} Tag value after python len comparison"""
    template = '{{ if len([variable]) == 5 }} foo {{ endif }}'
    self.assertEqual(self.parse(template, variable=[1,2,3,4,5]).strip(), 'foo')

  def testCompareNotallowdPythonFunction(self):
    """{{ if }} Tag value after python len comparison"""
    template = '{{ if open([variable]) == 5 }} foo {{ endif }}'
    self.assertRaises(templateparser.TemplateEvaluationError, self.parse, template)

  def testDefaultElse(self):
    """{{ if }} Else block will be parsed when `if` fails"""
    template = '{{ if [var] }}foo{{ else }}bar{{ endif }}'
    self.assertEqual(self.parse(template, var=True), 'foo')
    self.assertEqual(self.parse(template, var=False), 'bar')

  def testElif(self):
    """{{ if }} Elif blocks will be parsed until one matches"""
    template = """
        {{ if [var] == 1 }}a
        {{ elif [var] == 2 }}b
        {{ elif [var] == 3 }}c
        {{ elif [var] == 4 }}d
        {{ endif }}"""
    self.assertEqual(self.parse(template, var=1).strip(), 'a')
    self.assertEqual(self.parse(template, var=2).strip(), 'b')
    self.assertEqual(self.parse(template, var=3).strip(), 'c')
    self.assertEqual(self.parse(template, var=4).strip(), 'd')
    self.assertFalse(self.parse(template, var=5).strip())

  def testIfElifElse(self):
    """{{ if }} Full if/elif/else branch is functional all work"""
    template = """
        {{ if [var] == "a" }}1
        {{ elif [var] == "b"}}2
        {{ else }}3 {{ endif }}"""
    self.assertEqual(self.parse(template, var='a').strip(), '1')
    self.assertEqual(self.parse(template, var='b').strip(), '2')
    self.assertEqual(self.parse(template, var='c').strip(), '3')

  def testSyntaxErrorNoEndif(self):
    """{{ if }} Conditional without {{ endif }} raises TemplateSyntaxError"""
    template = '{{ if [var] }} foo'
    self.assertRaises(templateparser.TemplateSyntaxError, self.parse, template)

  def testSyntaxErrorElifAfterElse(self):
    """{{ if }} An `elif` clause following `else` raises TemplateSyntaxError"""
    template = '{{ if [var] }} {{ else }} {{ elif [var] }} {{ endif }}'
    self.assertRaises(templateparser.TemplateSyntaxError, self.parse, template)

  def testSyntaxErrorDoubleElse(self):
    """{{ if }} Starting a second `else` clause raises TemplateSyntaxError"""
    template = '{{ if [var] }} {{ else }} {{ else }} {{ endif }}'
    self.assertRaises(templateparser.TemplateSyntaxError, self.parse, template)

  def testSyntaxErrorClauseWithoutIf(self):
    """{{ if }} elif / else / endif without `if` raises TemplateSyntaxError"""
    template = '{{ elif }}'
    self.assertRaises(templateparser.TemplateSyntaxError, self.parse, template)
    template = '{{ else }}'
    self.assertRaises(templateparser.TemplateSyntaxError, self.parse, template)
    template = '{{ endif }}'
    self.assertRaises(templateparser.TemplateSyntaxError, self.parse, template)

  def testTagPresence(self):
    """{{ if }} Clauses require the tag to be present as a replacement"""
    template = '{{ if [absent] }} {{ endif }}'
    self.assertRaises(templateparser.TemplateNameError, self.parse, template)

  def testVariableMustBeTag(self):
    """{{ if }} Clauses must reference variables using a tag, not a name"""
    good_template = '{{ if [var] }} x {{ else }} x {{ endif }}'
    self.assertTrue(self.parse(good_template, var='foo'))
    bad_template = '{{ if var }} x {{ else }} x {{ endif }}'
    self.assertRaises(templateparser.TemplateNameError,
                      self.parse, bad_template, var='foo')

  def testLazyEvaluation(self):
    """{{ if }} Variables are retrieved in lazy fashion, not before needed"""
    # Tags are looked up lazily
    template = '{{ if [present] or [absent] }}~{{ endif }}'
    self.assertEqual(self.parse(template, present=True), '~')

    # Indices are looked up lazily
    template = '{{ if [var:present] or [var:absent] }}~{{ endif }}'
    self.assertEqual(self.parse(template, var={'present': 1}), '~')


class TemplateLoops(unittest.TestCase):
  """TemplateParser properly handles for-loops."""
  def setUp(self):
    """Sets up a testbed."""
    self.parser = templateparser.Parser()
    self.parse = self.parser.ParseString
    self.tmpl = templateparser.Template

  def testLoopCount(self):
    """{{ for }} Parser will loop once for each item in the for loop"""
    template = '{{ for num in [values] }}x{{ endfor }}'
    result = self.parse(template, values=range(5))
    self.assertEqual(result, 'xxxxx')

  def testLoopReplaceBasic(self):
    """{{ for }} The loop variable is available via tagname"""
    template = '{{ for num in [values] }}[num],{{ endfor }}'
    result = self.parse(template, values=range(5))
    self.assertEqual(result, '0,1,2,3,4,')

  def testLoopReplaceScope(self):
    """{{ for }} The loop variable overwrites similar names from outer scope"""
    template = '[num], {{ for num in [numbers] }}[num], {{ endfor }}[num]'
    result = self.parse(template, numbers=range(5), num='OUTER')
    self.assertEqual(result, 'OUTER, 0, 1, 2, 3, 4, OUTER')

  def testLoopOverIndexedTag(self):
    """{{ for }} Loops can be performed over indexed tags"""
    template = '{{ for num in [numbers:1] }}x{{ endfor }}'
    result = self.parse( template, numbers=[range(10), range(5), range(10)])
    self.assertEqual(result, 'xxxxx')

  def testLoopVariableIndex(self):
    """{{ for }} Loops variable tags support indexing and functions"""
    template = '{{ for bundle in [bundles]}}[bundle:1:name|upper], {{ endfor }}'
    bundles = [('1', {'name': 'Spam'}), ('2', {'name': 'Eggs'})]
    result = 'SPAM, EGGS, '
    self.parser.RegisterFunction('upper', str.upper)
    self.assertEqual(self.parse(template, bundles=bundles), result)

  def testLoopOnFunctions(self):
    """{{ for }} Loops work on function results if functions are used"""
    template = ('{{ for item in [mapping|items|sorted] }}'
                '[item:0]=[item:1] {{ endfor }}')
    mapping = {'first': 12, 'second': 42}
    result = 'first=12 second=42 '
    self.assertEqual(self.parse(template, mapping=mapping), result)
    # Assert that without sorted, this actually fails
    unsorted = ('{{ for item in [mapping|items] }} '
                '[item:0]=[item:1]{{ endfor }}')
    self.assertNotEqual(self.parse(unsorted, mapping=mapping), result)

  def testLoopTupleAssignment(self):
    """{{ for }} Loops support tuple unpacking for iterators"""
    template = ('{{ for key,val in [mapping|items|sorted] }}'
                '[key]=[val] {{ endfor }}')
    mapping = {'first': 12, 'second': 42}
    result = 'first=12 second=42 '
    self.assertEqual(self.parse(template, mapping=mapping), result)

  def testLoopTupleAssignmentMismatch(self):
    """{{ for }} Loops raise TemplateValueError when tuple unpacking fails"""
    template = '{{ for a, b, c in [iterator] }}[a]{{ endfor }}'
    self.assertEqual(self.parse(template, iterator=['xyz']), 'x')
    self.assertRaises(templateparser.TemplateValueError,
                      self.parse, template, iterator=['eggs'])
    self.assertRaises(templateparser.TemplateValueError,
                      self.parse, template, iterator=range(10))

  def testLoopTagPresence(self):
    """{{ for }} Loops require the loop tag to be present"""
    template = '{{ for item in [absent] }} hello {{ endfor }}'
    self.assertRaises(templateparser.TemplateNameError, self.parse, template)

  def testLoopAbsentIndex(self):
    """{{ for }} Loops over an absent index result in no loops (no error)"""
    template = '{{ for item in [tag:absent] }} x {{ endfor }}'
    self.assertFalse(self.parse(template, tag='absent'))


class TemplateTagPresenceCheck(unittest.TestCase):
  """Test cases for the `ifpresent` TemplateParser construct."""
  def setUp(self):
    self.parser = templateparser.Parser()
    self.parse = self.parser.ParseString
    self.templatefilename = 'ifpresent.utp'

  def testBasicTagPresence(self):
    """{{ ifpresent }} runs the code block if the tag is present"""
    template = '{{ ifpresent [tag] }} hello {{ endif }}'
    self.assertEqual(self.parse(template, tag='spam'), ' hello ')

  def testBasicTagAbsence(self):
    """{{ ifpresent }} does not run the main block if the tag is missing"""
    template = '{{ ifpresent [tag] }} hello {{ endif }}'
    self.assertFalse(self.parse(template))

  def testBasicTagNotPresence(self):
    """{{ ifnotpresent }} runs the code block if the tag is present"""
    template = '{{ ifnotpresent [tag] }} hello {{ endif }}'
    self.assertEqual(self.parse(template, othertag='spam'), ' hello ')

  def testNestedNotPresence(self):
    """{{ ifnotpresent }} runs the code block if the tag is present"""
    template = """{{ ifnotpresent [tag] }}
      {{ ifnotpresent [nestedtag] }}
        hello
      {{ endif }}
    {{ endif }}"""
    self.assertEqual(self.parse(template, othertag='spam').strip(), 'hello')

  def testTagPresenceElse(self):
    """{{ ifpresent }} has a functioning `else` clause"""
    template = '{{ ifpresent [tag] }} yes {{ else }} no {{ endif }}'
    self.assertEqual(self.parse(template, tag='spam'), ' yes ')
    self.assertEqual(self.parse(template), ' no ')

  def testPresenceElif(self):
    """{{ ifpresent }} has functioning `elif` support"""
    template = ('{{ ifpresent [one] }} first '
                '{{ elif [two] }} second {{ else }} third {{ endif }}')
    self.assertEqual(self.parse(template, one='present'), ' first ')
    self.assertEqual(self.parse(template, two='ready'), ' second ', )
    self.assertEqual(self.parse(template), ' third ')

  def testPresenceOfKey(self):
    """{{ ifpresent }} also works on index selectors"""
    template = '{{ ifpresent [tag:6] }} yes {{ else }} no {{ endif }}'
    self.assertEqual(self.parse(template, tag='longtext'), ' yes ')
    self.assertEqual(self.parse(template, tag='short'), ' no ')
    self.assertEqual(self.parse(template), ' no ')

  def testMultiTagPresence(self):
    """{{ ifpresent }} checks the presence of *all* provided tagnames/indices"""
    template = '{{ ifpresent [one] [two] }} good {{ endif }}'
    self.assertEqual(self.parse(template, one=1, two=2), ' good ')
    self.assertFalse(self.parse(template, one=1))
    self.assertFalse(self.parse(template, two=2))

  def testBadSyntax(self):
    """{{ ifpresent }} requires proper tags to be checked for presence"""
    template = '{{ ifpresent var }} {{ endif }}'
    self.assertRaises(templateparser.TemplateSyntaxError, self.parse, template)

  def testMultiTagPresenceFile(self):
    """{{ ifpresent }} checks if multiple runs on a file template containing an
    Ifpresent block work"""

    template = '{{ ifpresent [one] }} [one] {{ endif }}Blank'
    with open(self.templatefilename, 'w') as templatefile:
      templatefile.write(template)
    self.assertEqual(self.parser.Parse(self.templatefilename), 'Blank')
    #self.assertEqual(self.parser.Parse(self.templatefilename), 'Blank')
    #self.assertEqual(self.parser.Parse(self.templatefilename, one=1), ' 1 Blank')

  def tearDown(self):
    for tmpfile in (self.templatefilename, ):
      if os.path.exists(tmpfile):
        if os.path.isdir(tmpfile):
          os.rmdir(tmpfile)
        else:
          os.unlink(tmpfile)


class TemplateStringRepresentations(unittest.TestCase):
  """Test cases for string representation of various TemplateParser parts."""
  def setUp(self):
    self.strip = lambda string: re.sub('\s', '', string)
    self.tmpl = templateparser.Template
    self.parser = templateparser.Parser()

  def testTemplateTag(self):
    """[Representation] TemplateTags str() echoes its literal"""
    template = '[greeting] [title|casing] [person:name|casing] har'
    self.assertEqual(self.strip(str(self.tmpl(template))), self.strip(template))

  def testTemplateConditional(self):
    """[Representation] TemplateConditional str() echoes its literal"""
    template = '{{ if [a] == "foo" }} foo [b] {{ else }} bar [b] {{ endif }}'
    self.assertEqual(self.strip(str(self.tmpl(template))), self.strip(template))

  def testTemplateInline(self):
    """[Representation] TemplateInline str() shows the inlined template part"""
    example = 'Hello [location]'
    template = '{{ inline example }}'
    self.parser['example'] = self.tmpl(example)
    self.assertEqual(self.strip(str(self.tmpl(template, parser=self.parser))),
                     self.strip(example))

  def testTemplateLoop(self):
    """[Representation] TemplateLoop str() echoes its definition"""
    template = ('{{ for a, b in [iter|items] }}{{ for c in [a] }}[c]'
                '{{ endfor }}{{ endfor }}')
    self.assertEqual(self.strip(str(self.tmpl(template))), self.strip(template))


class TemplateNestedScopes(unittest.TestCase):
  """Test cases for nested function scopes."""
  def setUp(self):
    """Sets up a testbed."""
    self.parser = templateparser.Parser()
    self.parse = self.parser.ParseString
    self.tmpl = templateparser.Template

  def testLoopWithInline(self):
    """{{ nested }} Loops can contain an {{ inline }} section"""
    inline = '<li>Hello [name]</li>'
    self.parser['name'] = self.tmpl(inline)
    template = '{{ for name in [names] }}{{ inline name }}{{ endfor }}'
    result = self.parse(template, names=('John', 'Eric'))
    self.assertEqual(result, '<li>Hello John</li><li>Hello Eric</li>')

  def testLoopWithInlineLoop(self):
    """{{ nested }} Loops can contain {{ inline }} loops"""
    inline = '{{ for char in [name] }}[char].{{ endfor }}'
    self.parser['name'] = self.tmpl(inline)
    template = '{{ for name in [names] }}<li>{{ inline name }}</li>{{ endfor }}'
    result = self.parse(template, names=('John', 'Eric'))
    self.assertEqual(result, '<li>J.o.h.n.</li><li>E.r.i.c.</li>')

  def testInlineLoopsInConditional(self):
    """{{ nested }} Inlined loop in a conditional without problems"""
    self.parser['loop'] = self.tmpl('{{ for i in [loops] }}[i]{{ endfor }}')
    self.parser['once'] = self.tmpl('value: [value]')
    tmpl = '{{ if [x] }}{{ inline loop }}{{ else }}{{ inline once }}{{ endif }}'
    result_loop = self.parse(tmpl, loops=range(1, 6), x=True)
    result_once = self.parse(tmpl, value='foo', x=False)
    self.assertEqual(result_loop, '12345')
    self.assertEqual(result_once, 'value: foo')


class TemplateReloading(unittest.TestCase):
  """Tests for FileTemplate automatic reloading upon modification."""
  def setUp(self):
    self.simple = 'simple.html'
    self.simple_raw = 'simple [noun]'
    self.loop = 'loop.html'
    self.loop_raw = '{{ for bit in [blob] }}{{ inline simple.html }}{{ endfor }}'
    with open(self.simple, 'w') as simple:
      simple.write(self.simple_raw)
    with open(self.loop, 'w') as loop:
      loop.write(self.loop_raw)
    self.parser = templateparser.Parser()
    self.parser.AddTemplate(self.simple)
    self.parser.AddTemplate(self.loop)

  def tearDown(self):
    for tmpfile in (self.loop, self.simple):
      if os.path.exists(tmpfile):
        if os.path.isdir(tmpfile):
          os.rmdir(tmpfile)
        else:
          os.unlink(tmpfile)

  def testFileBasicReload(self):
    """[Reload] Template file is reloaded from disk after updating"""
    first = self.parser[self.simple].Parse()
    self.assertEqual(first, self.simple_raw)
    with open(self.simple, 'w') as new_template:
      new_template.write('new content')
      time.sleep(.01) # short pause so that mtime will actually be different
    second = self.parser[self.simple].Parse()
    self.assertEqual(second, 'new content')

  def testInlineReload(self):
    """[Reload] Inlined templates are not automatically reloaded"""
    first = self.parser[self.loop].Parse(blob='four')
    self.assertEqual(first, self.simple_raw * 4)
    with open(self.simple, 'w') as new_template:
      new_template.write('new content')
      time.sleep(.01) # short pause so that mtime will actually be different
    second = self.parser[self.loop].Parse(blob='four')
    self.assertEqual(second, 'new content' * 4)

  def testReloadDeletedTemplate(self):
    """[Reload] Deleted templates are not reloaded and don't trigger errors"""
    os.unlink(self.simple)
    self.assertEqual(self.parser[self.simple].Parse(), self.simple_raw)

  def testReplaceTemplateWithDirectory(self):
    """[Reload] Deleted templates are not reloaded and don't trigger errors"""
    os.unlink(self.simple)
    time.sleep(.01) # short pause so that mtime will actually be different
    os.mkdir(self.simple)
    self.assertEqual(self.parser[self.simple].Parse(), self.simple_raw)


class DictTemplateTagBasic(unittest.TestCase):
  """Tests validity and parsing of simple tags with dict output."""
  def setUp(self):
    """Makes the Template class available on the instance."""
    self.tmpl = templateparser.Template

  def testTaglessTemplate(self):
    """[BasicTag] Templates without tags get returned verbatim as SafeString"""
    template = 'Template without any tags'
    output = {'tags': {}, 'templatecontent': template}
    self.assertEqual(self.tmpl(template, dictoutput=True).Parse(), output)

  def testSingleTagTemplate(self):
    """[BasicTag] Templates with basic tags get returned proper"""
    template = 'Template with [single] tag'
    output = {'tags': {
                  '[single]': 'just one'
                },
              'templatecontent': template}
    result = self.tmpl(template, dictoutput=True).Parse(single='just one')
    self.assertEqual(result, output)

  def testSaveTagTemplate(self):
    """[BasicTag] Templates with basic tags get returned properly when replacement is already html safe"""
    template = 'Template with just [single] tag'
    output = {'tags': {
                  '[single]': '<b>a safe</b>'
                },
              'templatecontent': template}
    result = self.tmpl(template, dictoutput=True).Parse(single=templateparser.HTMLsafestring('<b>a safe</b>'))
    self.assertEqual(result, output)

  def testUnsaveTagTemplate(self):
    """[BasicTag] Templates with basic tags get returned properly when replacement is not html safe"""
    template = 'Template with just [single] tag'
    output = {'tags': {
                  '[single]': '&lt;b&gt;an unsafe&lt;/b&gt;'
                },
              'templatecontent': template}
    result = self.tmpl(template, dictoutput=True).Parse(single='<b>an unsafe</b>')
    self.assertEqual(result, output)

  def testCasedTag(self):
    """[BasicTag] Tag names are case-sensitive"""
    template = 'The parser has no trouble with [cAsE] [case].'
    output = {'tags': {
                  '[cAsE]': 'mixed',
                  '[case]': '[case]'
                },
              'templatecontent': template}

    result = self.tmpl(template, dictoutput=True).Parse(cAsE='mixed')
    self.assertEqual(result, output)

  def testUnderscoredTag(self):
    """[BasicTag] Tag names may contain underscores"""
    template = 'The template may contain [under_scored] tags.'
    output = {'tags': {
                  '[under_scored]': 'underscored'
                },
              'templatecontent': template}
    result = self.tmpl(template, dictoutput=True).Parse(under_scored='underscored')
    self.assertEqual(result, output)

  def testMultiTagTemplate(self):
    """[BasicTag] Multiple instances of a tag will all be replaced"""
    template = '[adjective] [noun] are better than other [noun].'
    output = {'tags': {
                  '[noun]': 'cows',
                  '[adjective]': 'Beefy'
                },
              'templatecontent': template}
    result = self.tmpl(template, dictoutput=True).Parse(noun='cows', adjective='Beefy')
    self.assertEqual(result, output)

  def testEmptyOrWhitespace(self):
    """[BasicTag] Empty tags or tags containing whitespace aren't actual tags"""
    template = 'This [is a] broken [] template, really'
    output = {'tags': {},
              'templatecontent': template}
    result = self.tmpl(template, dictoutput=True).Parse(**{'is a': 'HORRIBLY', '': ', NASTY'})
    self.assertEqual(result, output)

  def testBadCharacterTags(self):
    """[BasicTag] Tags containing bad characters are not considered tags"""
    bad_chars = """ :~!@#$%^&*()+-={}\|;':",./<>? """
    template = ''.join('[%s] [check]' % char for char in bad_chars)
    tags = {'[check]': '..'}
    replaces = {char: 'FAIL' for char in bad_chars}
    replaces['check'] = '..'
    output = {'tags': tags,
              'templatecontent': template}
    self.assertEqual(self.tmpl(template, dictoutput=True).Parse(**replaces), output)

  def testUnreplacedTag(self):
    """[BasicTag] Template tags without replacement are returned verbatim"""
    template = 'Template with an [undefined] tag.'
    output = {'tags': {},
              'templatecontent': template}
    self.assertEqual(self.tmpl(template, dictoutput=True).Parse(), output)

  def testUnreplacedTag(self):
    """[BasicTag] Access to private members is not allowed"""
    template = 'Template with an [private.__class__] tag.'
    output = {'tags': {},
              'templatecontent': template}
    self.assertEqual(self.tmpl(template, dictoutput=True).Parse(), output)

  def testBracketsInsideTag(self):
    """[BasicTag] Innermost bracket pair are the tag's delimiters"""
    template = 'Template tags may not contain [[spam][eggs]].'
    expected = 'Template tags may not contain [opening or closing brackets].'
    result = self.tmpl(template, dictoutput=True).Parse(
        **{'[spam': 'EPIC', 'eggs]': 'FAIL', 'spam][eggs': 'EPIC FAIL',
           'spam': 'opening or ', 'eggs': 'closing brackets'})
    output = {'tags': {
                '[spam]': 'opening or ',
                '[eggs]': 'closing brackets'
              },
              'templatecontent': template}
    self.assertEqual(output, result)

  def testTemplateInterpolationSyntax(self):
    """[BasicTag] Templates support string interpolation of dicts"""
    template = 'Hello [name]'
    output = {'tags': {
                  '[name]': 'Bob',
                },
              'templatecontent': template}
    self.assertEqual(self.tmpl(template, dictoutput=True) % {'name': 'Bob'}, output)

if __name__ == '__main__':
  unittest.main(testRunner=unittest.TextTestRunner(verbosity=2))
