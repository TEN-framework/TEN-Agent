package extension

func isPunctuation(r rune) bool {
	if r == ',' || r == '，' ||
		r == '.' || r == '。' ||
		r == '?' || r == '？' ||
		r == '!' || r == '！' {
		return true
	}
	return false
}

func parseSentence(sentence, content string) (string, string, bool) {
	var remain string
	var foundPunc bool

	for _, r := range content {
		if !foundPunc {
			sentence += string(r)
		} else {
			remain += string(r)
		}

		if !foundPunc && isPunctuation(r) {
			foundPunc = true
		}
	}

	return sentence, remain, foundPunc
}
