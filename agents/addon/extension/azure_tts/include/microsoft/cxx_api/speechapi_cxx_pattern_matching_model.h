//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_pattern_matching_model.h: Public API declarations for PatternMatchingModel C++ class
//

#pragma once
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_language_understanding_model.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_cxx_pattern_matching_intent.h>
#include <speechapi_cxx_pattern_matching_entity.h>
#include <speechapi_c_json.h>
#include <speechapi_c.h>
#include <fstream>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Intent {

    /// <summary>
    /// Represents a pattern matching model used for intent recognition.
    /// </summary>
    class PatternMatchingModel : public LanguageUnderstandingModel
    {
    public:

        /// <summary>
        /// Creates a pattern matching model using the specified model ID.
        /// </summary>
        /// <param name="modelId">A string that represents a unique Id for this model.</param>
        /// <returns>A shared pointer to pattern matching model.</returns>
        static std::shared_ptr<PatternMatchingModel> FromModelId(const SPXSTRING& modelId)
        {
            return std::shared_ptr<PatternMatchingModel> {
                new PatternMatchingModel(modelId)
            };
        }

        /// <summary>
        /// Creates a pattern matching model using the specified .json file. This should follow the Microsoft LUIS JSON export schema.
        /// </summary>
        /// <param name="filepath">A string that representing the path to a '.json' file.</param>
        /// <returns>A shared pointer to pattern matching model.</returns>
        static std::shared_ptr<PatternMatchingModel> FromJSONFile(const SPXSTRING& filepath)
        {
            FILE* fp;
            int err;
#ifdef _MSC_VER
            err = fopen_s(&fp, filepath.c_str(), "r");
#else
            fp = fopen(filepath.c_str(), "r");
            if (fp == NULL)
            {
                err = -1;
            }
            else
            {
                err = 0;
            }
#endif
            if (err == 0 && fp != NULL)
            {
                char buffer[1024] = {};
                size_t numread = 0;
                std::string fileContents = "";
#ifdef _MSC_VER
                while ((numread = fread_s((void**)&buffer, sizeof(buffer), sizeof(char), sizeof(buffer), fp)) != 0)
#else
                while ((numread = fread((void**)&buffer, sizeof(char), sizeof(buffer), fp)) != 0)
#endif
                {
                    fileContents.append(buffer, numread);
                }
                fclose(fp);
                return ParseJSONFile(fileContents);
            }
            else
            {
                SPX_TRACE_ERROR("Attempt to read %s failed.", SPXERR_FILE_OPEN_FAILED, filepath.c_str());
                return nullptr;
            }
        }

        /// <summary>
        /// Creates a PatternMatchingModel using the specified istream  pointing to an .json file in the LUIS json format.
        /// This assumes the stream is already open and has permission to read.
        /// </summary>
        /// <param name="iStream">A stream that representing a '.json' file.</param>
        /// <returns>A shared pointer to pattern matching model.</returns>
        static std::shared_ptr<PatternMatchingModel> FromJSONFileStream(std::istream& iStream)
        {
            std::istreambuf_iterator<char> iterator{iStream};
            std::string str(iterator, {});
            return ParseJSONFile(str);
        }

        /// <summary>
        /// Returns id for this model.
        /// </summary>
        /// <returns>A string representing the id of this model.</returns>
        SPXSTRING GetModelId() const { return m_modelId; }

        /// <summary>
        /// This container of Intents is used to define all the Intents this model will look for.
        /// </summary>
        std::vector<PatternMatchingIntent> Intents;

        /// <summary>
        /// This container of Intents is used to define all the Intents this model will look for.
        /// </summary>
        std::vector<PatternMatchingEntity> Entities;

    private:
        DISABLE_COPY_AND_MOVE(PatternMatchingModel);

        PatternMatchingModel(const SPXSTRING& modelId) : LanguageUnderstandingModel(LanguageUnderstandingModelType::PatternMatchingModel), m_modelId(modelId) {}

        SPXSTRING m_modelId;

        static std::shared_ptr<PatternMatchingModel> ParseJSONFile(const std::string& fileContents)
        {
            auto model = std::shared_ptr<PatternMatchingModel>(new PatternMatchingModel(""));
            AZAC_HANDLE parserHandle;
            auto root = ai_core_json_parser_create(&parserHandle, fileContents.c_str(), fileContents.size());
            if (!ai_core_json_parser_handle_is_valid(parserHandle))
            {
                SPX_TRACE_ERROR("Attempt to parse language understanding json file failed.", SPXERR_UNSUPPORTED_FORMAT);
                return nullptr;
            }
            int count = ai_core_json_item_count(parserHandle, root);
            for (int i = 0; i < count; i++)
            {
                auto itemInt = ai_core_json_item_at(parserHandle, root, i, nullptr);
                auto nameInt = ai_core_json_item_name(parserHandle, itemInt);
                size_t nameSize;
                auto name = ai_core_json_value_as_string_ptr(parserHandle, nameInt, &nameSize);

                size_t valueSize = 0;
                auto value = ai_core_json_value_as_string_ptr(parserHandle, itemInt, &valueSize);
                if (name != nullptr)
                {
                    auto nameStr = std::string(name, nameSize);
                    if (nameStr == "luis_schema_version")
                    {
                        // We support any version that we are able to pull data out of.
                    }
                    else if (nameStr == "prebuiltEntities")
                    {
                        int prebuiltcount = ai_core_json_item_count(parserHandle, itemInt);
                        for (int j = 0; j < prebuiltcount; j++)
                        {
                            ParsePrebuiltEntityJson(parserHandle, model, itemInt, j);
                        }
                    }
                    else if (nameStr == "name")
                    {
                        model->m_modelId = std::string(value, valueSize);
                    }
                    else if (nameStr == "patternAnyEntities" || nameStr == "entities")
                    {
                        int anyCount = ai_core_json_item_count(parserHandle, itemInt);
                        for (int j = 0; j < anyCount; j++)
                        {
                            ParseEntityJson(parserHandle, model, itemInt, j);
                        }
                    }
                    else if (nameStr == "patterns")
                    {
                        int patternCount = ai_core_json_item_count(parserHandle, itemInt);
                        for (int j = 0; j < patternCount; j++)
                        {
                            ParsePatternJson(parserHandle, model, itemInt, j);
                        }
                    }
                    else if (nameStr == "closedLists")
                    {
                        int listCount = ai_core_json_item_count(parserHandle, itemInt);
                        for (int j = 0; j < listCount; j++)
                        {
                            ParseListEntityJson(parserHandle, model, itemInt, j);
                        }
                    }
                }
            }
            return model;
        }

        static void ParsePrebuiltEntityJson(AZAC_HANDLE parserHandle, std::shared_ptr<PatternMatchingModel> model, int itemInt, int index)
        {
            auto subItemInt = ai_core_json_item_at(parserHandle, itemInt, index, nullptr);
            int subItemCount = ai_core_json_item_count(parserHandle, subItemInt);
            size_t nameSize = 0;
            size_t valueSize = 0;
            for (int subItemIndex = 0; subItemIndex < subItemCount; subItemIndex++)
            {
                auto prebuiltPairInt = ai_core_json_item_at(parserHandle, subItemInt, subItemIndex, nullptr);
                auto nameInt = ai_core_json_item_name(parserHandle, prebuiltPairInt);
                auto name = ai_core_json_value_as_string_ptr(parserHandle, nameInt, &nameSize);
                if (name != nullptr)
                {
                    auto nameStr = std::string(name, nameSize);
                    auto value = ai_core_json_value_as_string_ptr(parserHandle, prebuiltPairInt, &valueSize);
                    if (nameStr == "name" && value != nullptr)
                    {
                        auto valueStr = std::string(value, valueSize);
                        if (valueStr == "number")
                        {
                            model->Entities.push_back({ "number", EntityType::PrebuiltInteger, EntityMatchMode::Basic, {} });
                        }
                        // ignore any other prebuilt types as they are not supported.
                    }
                }
            }
        }

        static void ParseEntityJson(AZAC_HANDLE parserHandle, std::shared_ptr<PatternMatchingModel> model, int itemInt, int index)
        {
            auto subItemInt = ai_core_json_item_at(parserHandle, itemInt, index, nullptr);
            int subItemCount = ai_core_json_item_count(parserHandle, subItemInt);
            size_t nameSize = 0;
            size_t valueSize = 0;
            for (int subItemIndex = 0; subItemIndex < subItemCount; subItemIndex++)
            {
                auto entityPairInt = ai_core_json_item_at(parserHandle, subItemInt, subItemIndex, nullptr);
                auto nameInt = ai_core_json_item_name(parserHandle, entityPairInt);
                auto name = ai_core_json_value_as_string_ptr(parserHandle, nameInt, &nameSize);
                if (name != nullptr)
                {
                    auto nameStr = std::string(name, nameSize);
                    auto value = ai_core_json_value_as_string_ptr(parserHandle, entityPairInt, &valueSize);
                    if (nameStr == "name" && value != nullptr)
                    {
                        model->Entities.push_back({ std::string(value, valueSize), EntityType::Any, EntityMatchMode::Basic, {}});
                    }
                    // ignore any other pairs since we only care about the name.
                }
            }
        }

        static void ParseListEntityJson(AZAC_HANDLE parserHandle, std::shared_ptr<PatternMatchingModel> model, int itemInt, int index)
        {
            auto subItemInt = ai_core_json_item_at(parserHandle, itemInt, index, nullptr);
            int subItemCount = ai_core_json_item_count(parserHandle, subItemInt);
            size_t nameSize = 0;
            size_t valueSize = 0;
            // Default to Strict matching.
            PatternMatchingEntity entity{ "", EntityType::List, EntityMatchMode::Strict, {} };
            for (int subItemIndex = 0; subItemIndex < subItemCount; subItemIndex++)
            {
                auto listPairInt = ai_core_json_item_at(parserHandle, subItemInt, subItemIndex, nullptr);
                auto nameInt = ai_core_json_item_name(parserHandle, listPairInt);
                auto name = ai_core_json_value_as_string_ptr(parserHandle, nameInt, &nameSize);
                if (name != nullptr)
                {
                    auto nameStr = std::string(name, nameSize);
                    if (nameStr == "name")
                    {
                        auto value = ai_core_json_value_as_string_ptr(parserHandle, listPairInt, &valueSize);
                        if (value != nullptr)
                        {
                            entity.Id = std::string(value, valueSize);
                        }
                    }
                    if (nameStr == "subLists")
                    {
                        ParseSubList(parserHandle, entity, listPairInt);
                    }
                    // ignore any other pairs since we only care about the name.
                }
            }
            model->Entities.push_back(entity);
        }

        static void ParseSubList(AZAC_HANDLE parserHandle, PatternMatchingEntity& entity, int listPairInt) 
        {
            size_t nameSize = 0;
            size_t valueSize = 0;
            auto subListCount = ai_core_json_item_count(parserHandle, listPairInt);
            for (int subListIndex = 0; subListIndex < subListCount; subListIndex++)
            {
                auto subListItemInt = ai_core_json_item_at(parserHandle, listPairInt, subListIndex, nullptr);
                auto subListItemCount = ai_core_json_item_count(parserHandle, subListItemInt);
                for (int subListItemIndex = 0; subListItemIndex < subListItemCount; subListItemIndex++)
                {
                    auto subListPairInt = ai_core_json_item_at(parserHandle, subListItemInt, subListItemIndex, nullptr);
                    auto nameInt = ai_core_json_item_name(parserHandle, subListPairInt);
                    auto name = ai_core_json_value_as_string_ptr(parserHandle, nameInt, &nameSize);
                    if (name != nullptr)
                    {
                        auto nameStr = std::string(name, nameSize);
                        if (nameStr == "canonicalForm")
                        {
                            auto value = ai_core_json_value_as_string_ptr(parserHandle, subListPairInt, &valueSize);
                            if (value != nullptr)
                            {
                                entity.Phrases.push_back(std::string(value, valueSize));
                            }
                        }
                        else if (nameStr == "list")
                        {
                            auto subListSynonymInt = ai_core_json_item_at(parserHandle, subListItemInt, subListItemIndex, nullptr);
                            auto subListSynonymItemCount = ai_core_json_item_count(parserHandle, subListSynonymInt);
                            for (int subListSynonymIndex = 0; subListSynonymIndex < subListSynonymItemCount; subListSynonymIndex++)
                            {
                                auto subListSynonymEntryInt = ai_core_json_item_at(parserHandle, subListSynonymInt, subListSynonymIndex, nullptr);
                                auto value = ai_core_json_value_as_string_ptr(parserHandle, subListSynonymEntryInt, &valueSize);
                                if (value != nullptr)
                                {
                                    entity.Phrases.push_back(std::string(value, valueSize));
                                }
                            }
                        }
                    }
                }
            }
        }

        static void ParsePatternJson(AZAC_HANDLE parserHandle, std::shared_ptr<PatternMatchingModel> model, int itemInt, int index)
        {
            auto subItemInt = ai_core_json_item_at(parserHandle, itemInt, index, nullptr);
            int subItemCount = ai_core_json_item_count(parserHandle, subItemInt);
            size_t nameSize = 0;
            size_t valueSize = 0;
            std::string patternStr, intentIdStr;
            for (int subItemIndex = 0; subItemIndex < subItemCount; subItemIndex++)
            {
                auto entityPairInt = ai_core_json_item_at(parserHandle, subItemInt, subItemIndex, nullptr);
                auto nameInt = ai_core_json_item_name(parserHandle, entityPairInt);
                auto name = ai_core_json_value_as_string_ptr(parserHandle, nameInt, &nameSize);
                if (name != nullptr)
                {
                    auto nameStr = std::string(name, nameSize);
                    auto value = ai_core_json_value_as_string_ptr(parserHandle, entityPairInt, &valueSize);
                    if (value != nullptr)
                    {
                        if (nameStr == "pattern")
                        {
                            patternStr = std::string(value, valueSize);
                        }
                        else if (nameStr == "intent")
                        {
                            intentIdStr = std::string(value, valueSize);
                        }
                    }
                    // ignore any other pairs since we only care about the name.
                }
            }
            if (!patternStr.empty() && !intentIdStr.empty())
            {
                bool added = false;
                for (auto& intent : model->Intents)
                {
                    if (intent.Id == intentIdStr)
                    {
                        intent.Phrases.push_back(patternStr);
                        added = true;
                        break;
                    }
                }
                if (!added)
                {
                    model->Intents.push_back({ {patternStr}, intentIdStr});
                }
            }
        }

};

} } } } // Microsoft::CognitiveServices::Speech::Intent
