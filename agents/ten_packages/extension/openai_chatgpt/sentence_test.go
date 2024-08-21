package extension

import (
	"strings"
	"testing"

	"github.com/stretchr/testify/require"
)

func TestIsPunctuation(t *testing.T) {
	cases := []struct {
		r      rune
		expect bool
	}{
		{',', true},
		{'，', true},
		{'.', true},
		{'。', true},
		{'?', true},
		{'？', true},
		{'!', true},
		{'！', true},

		{'a', false},
		{'0', false},
	}

	for i, c := range cases {
		require.Equal(t, c.expect, isPunctuation(c.r), "case %d", i)
	}
}

func TestSplitByPunctuation(t *testing.T) {
	cases := []struct {
		s      string
		expect []string
	}{
		{"Hello world!", []string{"Hello world"}},
		{"Hey, there!", []string{"Hey", " there"}},
	}

	for i, c := range cases {
		out := strings.FieldsFunc(c.s, isPunctuation)
		require.Equal(t, c.expect, out, "case %d", i)
	}
}

func TestParseSentence_Should_NoFinalSentence(t *testing.T) {
	cases := []struct {
		sentence string
		content  string

		expectSentence string
		expectContent  string
	}{
		{
			sentence:       "",
			content:        "",
			expectSentence: "",
			expectContent:  "",
		},
		{
			sentence:       "a",
			content:        "",
			expectSentence: "a",
			expectContent:  "",
		},
		{
			sentence:       "",
			content:        "a",
			expectSentence: "a",
			expectContent:  "",
		},
		{
			sentence:       "abc",
			content:        "ddd",
			expectSentence: "abcddd",
			expectContent:  "",
		},
	}

	for i, c := range cases {
		sentence, content, final := parseSentence(c.sentence, c.content)
		require.False(t, final, "case %d", i)

		require.Equal(t, c.expectSentence, sentence, "case %d", i)
		require.Equal(t, c.expectContent, content, "case %d", i)
	}
}

func TestParseSentence_Should_FinalSentence(t *testing.T) {
	cases := []struct {
		sentence string
		content  string

		expectSentence string
		expectContent  string
	}{
		{
			sentence:       "",
			content:        ",",
			expectSentence: ",",
			expectContent:  "",
		},
		{
			sentence:       "",
			content:        ",ddd",
			expectSentence: ",",
			expectContent:  "ddd",
		},
		{
			sentence:       "abc",
			content:        ",ddd",
			expectSentence: "abc,",
			expectContent:  "ddd",
		},
		{
			sentence:       "abc",
			content:        "dd,d",
			expectSentence: "abcdd,",
			expectContent:  "d",
		},
		{
			sentence:       "abc",
			content:        "ddd,",
			expectSentence: "abcddd,",
			expectContent:  "",
		},
		{
			sentence:       "abc",
			content:        "ddd,eee,fff,",
			expectSentence: "abcddd,",
			expectContent:  "eee,fff,",
		},
		{
			sentence:       "我的",
			content:        "你好，啊！",
			expectSentence: "我的你好，",
			expectContent:  "啊！",
		},
	}

	for i, c := range cases {
		sentence, content, final := parseSentence(c.sentence, c.content)
		require.True(t, final, "case %d", i)

		require.Equal(t, c.expectSentence, sentence, "case %d", i)
		require.Equal(t, c.expectContent, content, "case %d", i)
	}
}
