//
// Copyright (c) Microsoft. All rights reserved.
// See https://aka.ms/csspeech/license for the full license information.
//
// speechapi_cxx_user.h: Public API declarations for User C++ class
//

#pragma once

#include <cstring>

namespace Microsoft {
namespace CognitiveServices {
namespace Speech {
namespace Transcription {

constexpr size_t MAX_USER_ID_LEN = 1024;

/// <summary>
/// Represents a user in a conversation.
/// Added in version 1.5.0.
/// </summary>
class User
{
public:

    /// <summary>
    /// Create a user with identification string.
    /// </summary>
    /// <param name="userId">A user id.</param>
    /// <returns>A user object</returns>
    static std::shared_ptr<User> FromUserId(const SPXSTRING& userId)
    {
        SPXUSERHANDLE m_huser = SPXHANDLE_INVALID;
        SPX_THROW_ON_FAIL(user_create_from_id(Utils::ToUTF8(userId).c_str(), &m_huser));
        return std::make_shared<User>(m_huser);
    }

    /// <summary>
    /// Internal constructor. Creates a new instance using the provided handle.
    /// </summary>
    /// <param name="huser">A user handle.</param>
    explicit User(SPXUSERHANDLE huser = SPXHANDLE_INVALID) : m_huser(huser) { }

    /// <summary>
    /// Virtual destructor.
    /// </summary>
    virtual ~User() { user_release_handle(m_huser); }

    /// <summary>
    /// Internal. Explicit conversion operator.
    /// </summary>
    /// <returns>A handle.</returns>
    explicit operator SPXUSERHANDLE() const { return m_huser; }

    /// <summary>
    /// Get user's id.
    /// </summary>
    /// <returns>user's id.</returns>
    SPXSTRING GetId() const
    {
        char user_id[MAX_USER_ID_LEN+1];
        std::memset(user_id, 0, MAX_USER_ID_LEN+1);
        SPX_THROW_ON_FAIL(user_get_id(m_huser, user_id, MAX_USER_ID_LEN));

        return user_id;
    }

private:

    DISABLE_COPY_AND_MOVE(User);

    SPXUSERHANDLE m_huser;

};

}}}}
