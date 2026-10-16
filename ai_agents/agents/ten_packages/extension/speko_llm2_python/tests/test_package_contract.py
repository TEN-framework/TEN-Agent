def test_real_addon_registration():
    from speko_llm2_python import addon
    from ten_runtime.addon_manager import _AddonManager

    assert callable(_AddonManager._registry["speko_llm2_python"])
    assert addon.__file__.endswith("addon.py")
