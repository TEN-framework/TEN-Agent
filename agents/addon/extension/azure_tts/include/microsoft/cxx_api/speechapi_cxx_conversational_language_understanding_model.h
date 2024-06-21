//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license201809 for the full license information.
//
// speechapi_cxx_conversational_language_understanding_model.h: Public API declarations for PatternMatchingModel C++ class
//

#pragma once
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_language_understanding_model.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_c.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Intent {

    /// <summary>
    /// Represents a Conversational Language Understanding used for intent recognition.
    /// </summary>
    class ConversationalLanguageUnderstandingModel : public LanguageUnderstandingModel
    {
    public:

        /// <summary>
        /// Creates a Conversational Language Understanding (CLU) model using the specified model ID.
        /// </summary>
        /// <param name="languageResourceKey">The Azure Language resource key.</param>
        /// <param name="endpoint">The Azure Language resource endpoint.</param>
        /// <param name="projectName">The Conversational Language Understanding project name.</param>
        /// <param name="deploymentName">The Conversational Language Understanding deployment name.</param>
        /// <returns>A shared pointer to the Conversational Language Understanding model.</returns>
        static std::shared_ptr<ConversationalLanguageUnderstandingModel> FromResource(const SPXSTRING& languageResourceKey, const SPXSTRING& endpoint, const SPXSTRING& projectName, const SPXSTRING& deploymentName)
        {
            return std::shared_ptr<ConversationalLanguageUnderstandingModel> {
                new ConversationalLanguageUnderstandingModel(languageResourceKey, endpoint, projectName, deploymentName)
            };
        }

        /// <summary>
        /// Returns id for this model. Defaults to projectName-deploymentName.
        /// </summary>
        /// <returns>A string representing the id of this model.</returns>
        SPXSTRING GetModelId() const { return m_modelId; }

        /// <summary>
        /// Sets the id for this model. Defaults to projectName-deploymentName.
        /// </summary>
        /// <param name="value">A string representing the id of this model.</param>
        void SetModelId(SPXSTRING value) { m_modelId = value; }

        /// <summary>
        /// This is the Azure language resource key to be used with this model.
        /// </summary>
        SPXSTRING languageResourceKey;

        /// <summary>
        /// Conversational Language Understanding deployment endpoint to contact.
        /// </summary>
        SPXSTRING endpoint;

        /// <summary>
        /// Conversational Language Understanding project name.
        /// </summary>
        SPXSTRING projectName;

        /// <summary>
        /// Conversational Language Understanding deployment name.
        /// </summary>
        SPXSTRING deploymentName;

    private:
        DISABLE_COPY_AND_MOVE(ConversationalLanguageUnderstandingModel);

        ConversationalLanguageUnderstandingModel(const SPXSTRING& languageResourceKey, const SPXSTRING& endpoint, const SPXSTRING& projectName, const SPXSTRING& deploymentName) :
            LanguageUnderstandingModel(LanguageUnderstandingModelType::ConversationalLanguageUnderstandingModel),
            languageResourceKey(languageResourceKey),
            endpoint(endpoint),
            projectName(projectName),
            deploymentName(deploymentName)
        {
            m_modelId = projectName + "-" + deploymentName;
        }

        SPXSTRING m_modelId;
};

} } } } // Microsoft::CognitiveServices::Speech::Intent
