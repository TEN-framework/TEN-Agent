#!/bin/bash


pylint ./agents/ten_packages/extension/. || pylint-exit --warn-fail --error-fail $?