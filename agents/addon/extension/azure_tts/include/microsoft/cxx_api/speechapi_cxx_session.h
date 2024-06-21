//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_session.h: Public API declarations for Session C++ class
//

#pragma once
#include <exception>
#include <future>
#include <memory>
#include <string>
#include <speechapi_cxx_common.h>
#include <speechapi_c.h>
#include <speechapi_cxx_properties.h>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {

/*! \cond PRIVATE */

class Session
{
private:

    class PrivatePropertyCollection : public PropertyCollection
    {
    public:
        PrivatePropertyCollection(SPXSESSIONHANDLE hsession) :
            PropertyCollection(
                [=](){
                SPXPROPERTYBAGHANDLE hpropbag = SPXHANDLE_INVALID;
                session_get_property_bag(hsession, &hpropbag);
                return hpropbag;
            }())
        {
        }
    };

    PrivatePropertyCollection m_properties;

public:

    template <class T>
    static std::shared_ptr<Session> FromRecognizer(std::shared_ptr<T> recognizer)
    {
        SPX_INIT_HR(hr);

        SPXSESSIONHANDLE hsession = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(hr = ::session_from_recognizer(recognizer->m_hreco, &hsession));

        return std::make_shared<Session>(hsession);
    }

    explicit Session(SPXSESSIONHANDLE hsession) :
        m_properties(hsession),
        Properties(m_properties),
        m_hsession(hsession)
    {
        SPX_DBG_TRACE_FUNCTION();
    }

    virtual ~Session()
    {
        SPX_DBG_TRACE_FUNCTION();

        if (m_hsession != SPXHANDLE_INVALID)
        {
            ::session_handle_release(m_hsession);
            m_hsession = SPXHANDLE_INVALID;
        }
    }

    PropertyCollection& Properties;

private:

    DISABLE_COPY_AND_MOVE(Session);

    SPXSESSIONHANDLE m_hsession;
};

/*! \endcond */

} } } // Microsoft::CognitiveServices::Speech
