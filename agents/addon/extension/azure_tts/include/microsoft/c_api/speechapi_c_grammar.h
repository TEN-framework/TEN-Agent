//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_c_grammar.h: Public API declarations for Grammar related C methods and typedefs
//

#pragma once
#include <speechapi_c_common.h>

typedef enum
{
    // A Recognition Factor will apply to grammars that are referenced as individual words.
    PartialPhrase = 1
} GrammarList_RecognitionFactorScope;

SPXAPI_(bool) grammar_handle_is_valid(SPXGRAMMARHANDLE hgrammar);
SPXAPI phrase_list_grammar_from_recognizer_by_name(SPXGRAMMARHANDLE* hgrammar, SPXRECOHANDLE hreco, const char* name);
SPXAPI grammar_handle_release(SPXGRAMMARHANDLE hgrammar);

SPXAPI phrase_list_grammar_add_phrase(SPXGRAMMARHANDLE hgrammar, SPXPHRASEHANDLE hphrase);
SPXAPI phrase_list_grammar_clear(SPXGRAMMARHANDLE hgrammar);

SPXAPI_(bool) grammar_phrase_handle_is_valid(SPXPHRASEHANDLE hphrase);
SPXAPI grammar_phrase_create_from_text(SPXPHRASEHANDLE* hphrase, const char* phrase);
SPXAPI grammar_phrase_handle_release(SPXPHRASEHANDLE hphrase);

SPXAPI grammar_create_from_storage_id(SPXGRAMMARHANDLE *hgrammarlist, const char *id);
SPXAPI grammar_list_from_recognizer(SPXGRAMMARHANDLE *hgrammarlist, SPXRECOHANDLE hreco);
SPXAPI grammar_list_add_grammar(SPXGRAMMARHANDLE hgrammarlist, SPXGRAMMARHANDLE hgrammar);
SPXAPI grammar_list_set_recognition_factor(SPXGRAMMARHANDLE hgrammarlist, double factor, GrammarList_RecognitionFactorScope scope);
SPXAPI class_language_model_from_storage_id(SPXGRAMMARHANDLE* hclm, const char *storageid);
SPXAPI class_language_model_assign_class(SPXGRAMMARHANDLE hclm, const char *classname, SPXGRAMMARHANDLE hgrammar);
