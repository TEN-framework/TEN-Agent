//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_language_understanding_model.h: Public API declarations for LanguageUnderstandingModel C++ class
//

#pragma once
#include <speechapi_cxx_common.h>
#include <speechapi_cxx_string_helpers.h>
#include <speechapi_c.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Intent {

/// <summary>
/// Represents language understanding model used for intent recognition.
/// </summary>
class LanguageUnderstandingModel 
{
public:

    enum class LanguageUnderstandingModelType
    {
        PatternMatchingModel,
        LanguageUnderstandingModel,
        ConversationalLanguageUnderstandingModel
    };

    /// <summary>
    /// Creates a language understanding (LUIS) model using the specified endpoint url.
    /// </summary>
    /// <param name="uri">The endpoint url of a language understanding model.</param>
    /// <returns>A shared pointer to language understanding model.</returns>
    static std::shared_ptr<LanguageUnderstandingModel> FromEndpoint(const SPXSTRING& uri)
    {
        SPXLUMODELHANDLE hlumodel = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(language_understanding_model_create_from_uri(&hlumodel, Utils::ToUTF8(uri).c_str()));
        return std::make_shared<LanguageUnderstandingModel>(hlumodel);
    }

    /// <summary>
    /// Creates a language understanding model using the specified app id.
    /// </summary>
    /// <param name="appId">A string that represents the application id of Language Understanding service.</param>
    /// <returns>A shared pointer to language understanding model.</returns>
    static std::shared_ptr<LanguageUnderstandingModel> FromAppId(const SPXSTRING& appId)
    {
        SPXLUMODELHANDLE hlumodel = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(language_understanding_model_create_from_app_id(&hlumodel, Utils::ToUTF8(appId).c_str()));
        return std::make_shared<LanguageUnderstandingModel>(hlumodel);
    }

    /// <summary>
    /// Creates a language understanding model using the specified hostname, subscription key and application id.
    /// </summary>
    /// <param name="subscriptionKey">A string that represents the subscription key of Language Understanding service.</param>
    /// <param name="appId">A string that represents the application id of Language Understanding service.</param>
    /// <param name="region">A String that represents the region of the Language Understanding service (see the <a href="https://aka.ms/csspeech/region">region page</a>).</param>
    /// <returns>A shared pointer to language understanding model.</returns>
    static std::shared_ptr<LanguageUnderstandingModel> FromSubscription(const SPXSTRING& subscriptionKey, const SPXSTRING& appId, const SPXSTRING& region)
    {
        SPXLUMODELHANDLE hlumodel = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(language_understanding_model_create_from_subscription(&hlumodel, Utils::ToUTF8(subscriptionKey).c_str(), Utils::ToUTF8(appId).c_str(), Utils::ToUTF8(region).c_str()));
        return std::make_shared<LanguageUnderstandingModel>(hlumodel);
    }

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="hlumodel">Language understanding model handle.</param>
    explicit LanguageUnderstandingModel(SPXLUMODELHANDLE hlumodel = SPXHANDLE_INVALID) : m_type(LanguageUnderstandingModelType::LanguageUnderstandingModel), m_hlumodel(hlumodel)  { }

    /// <summary>
    /// Virtual destructor.
    /// </summary>
    virtual ~LanguageUnderstandingModel() { language_understanding_model__handle_release(m_hlumodel); }

    /// <summary>
    /// Internal. Explicit conversion operator.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXLUMODELHANDLE() const { return m_hlumodel; }

    /// <summary>
    /// Returns id for this model.
    /// </summary>
    /// <returns>An string representing the id of this model.</returns>
    virtual SPXSTRING GetModelId() const { return Utils::ToSPXString(language_understanding_model_get_model_id(m_hlumodel)); }

    /// <summary>
    /// Gets the model type.
    /// </summary>
    /// <returns>An enum representing the type of the model.</returns>
    LanguageUnderstandingModelType GetModelType() const { return m_type; }
protected:
    /// <summary>
    /// Protected constructor for base classes to set type.
    /// </summary>
    /// <param name="type">Language understanding model type.</param>
    LanguageUnderstandingModel(LanguageUnderstandingModelType type) : m_type(type), m_hlumodel(SPXHANDLE_INVALID){}

    LanguageUnderstandingModelType m_type;
private:
    DISABLE_COPY_AND_MOVE(LanguageUnderstandingModel);

    SPXLUMODELHANDLE m_hlumodel;
};


} } } } // Microsoft::CognitiveServices::Speech::Intent
