/**
 *
 * Agora Real Time Engagement
 * Created by Liu Loulou in 2024-04.
 * Copyright (c) 2024 Agora IO. All rights reserved.
 *
 */

package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"go/build"
	"io"
	"log"
	"os"
	"os/exec"
	"path"
	"reflect"
	"regexp"
	"runtime"
	"strconv"
	"strings"
)

const (
	AcquiredGoVersion string = "1.20"
	BackupGoMod       string = "_go.mod"
	BackupGoSum       string = "_go.sum"
)

func getAppDir() string {
	// Golang provides the following three ways to get the location of this
	// module:
	//
	// - filepath.Dir(os.Args[0])
	//
	// - os.Executable()
	//
	// - os.Getwd()
	//
	// However, this module might be executed using `go run scripts/build/*.go`,
	// a temporary executable will be built by Golang (ex:
	// /tmp/go-build2621984543/b001/exe/builder) in this case. And the first and
	// second methods will return the exactly path of the executable, in other
	// words, the temporary directory will be returned if this module is
	// executed using `go run` command.

	cwd, err := os.Getwd()
	if err != nil {
		log.Fatalf("Failed to get location of GO app, %v", err)
	}

	return cwd
}

func getAppPkgName(appDir string) string {
	pkg, err := build.ImportDir(appDir, build.AllowBinary)
	if err != nil {
		log.Fatalf("Failed to read GO package of app, %v", err)
	}

	return pkg.Name
}

func main() {
	// Setup logging.
	log.SetFlags(log.Ltime)

	options := &BuildOption{}
	flag.StringVar(
		&options.AppDir,
		"app_dir",
		getAppDir(),
		"The base directory of the GO app, used for debug.",
	)
	flag.StringVar(
		&options.AutoGenImportFile,
		"auto_gen_import_file",
		DefaultAutoImportFile,
		"The name of auto generated file used to import all addons.",
	)
	flag.BoolVar(
		&options.KeepAutoGen,
		"keep_auto_gen",
		false,
		"Whether to keep the auto-gen files.",
	)
	flag.BoolVar(
		&options.CleanAutoGen,
		"clean_auto_gen",
		false,
		"Clean the auto-gen files only, without building the app.",
	)
	flag.StringVar(
		&options.Mod,
		"mod",
		"",
		"Module download mode to use: readonly, vendor, or mod. Same as the -mod flag in go build.",
	)
	flag.StringVar(
		&options.GCFlags,
		"gcflags",
		"",
		"Flags to pass to the Go compiler. Same as the -gcflags flag in go build.",
	)
	flag.StringVar(
		&options.LdFlags,
		"ldflags",
		"",
		"Flags to pass to the Go linker. Same as the -ldflags flag in go build.",
	)
	flag.BoolVar(
		&options.EnableAsan,
		"asan",
		false,
		"Enable address sanitizer. Same as the -asan flag in go build.",
	)
	flag.BoolVar(
		&options.Verbose,
		"verbose",
		false,
		"Displays the verbose output.",
	)
	flag.Parse()

	if err := options.Valid(); err != nil {
		log.Fatalf("Invalid options: %v", err)
	}

	appPkgName := getAppPkgName(options.AppDir)
	ab := NewAppBuilder(appPkgName, AcquiredGoVersion, options)

	if options.CleanAutoGen {
		ab.Cleanup()
		log.Println("Clean auto-gen files successfully.")
		return
	}

	err := ab.Build()

	// No matter the build is successful or not, we need to cleanup the
	// temporary files.
	if !options.KeepAutoGen {
		ab.Cleanup()
	}

	if err != nil {
		log.Fatalf("Error: %v", err)
	} else {
		log.Println("Build GO app successfully.")
	}
}

// -------------- version ----------------

// Copy from https://github.com/hashicorp/go-version/blob/main/version.go.

// The compiled regular expression used to test the validity of a version.
var (
	versionRegexp *regexp.Regexp
)

// The raw regular expression string used for testing the validity
// of a version.
const (
	VersionRegexpRaw string = `v?([0-9]+(\.[0-9]+)*?)` +
		`(-([0-9]+[0-9A-Za-z\-~]*(\.[0-9A-Za-z\-~]+)*)|(-?([A-Za-z\-~]+[0-9A-Za-z\-~]*(\.[0-9A-Za-z\-~]+)*)))?` +
		`(\+([0-9A-Za-z\-~]+(\.[0-9A-Za-z\-~]+)*))?` +
		`?`
)

// Version represents a single version.
type Version struct {
	metadata string
	pre      string
	segments []int64
	si       int
	original string
}

func init() {
	versionRegexp = regexp.MustCompile("^" + VersionRegexpRaw + "$")
}

// NewVersion parses the given version and returns a new
// Version.
func NewVersion(v string) (*Version, error) {
	return newVersion(v, versionRegexp)
}

func newVersion(v string, pattern *regexp.Regexp) (*Version, error) {
	matches := pattern.FindStringSubmatch(v)
	if matches == nil {
		return nil, fmt.Errorf("malformed version: %s", v)
	}
	segmentsStr := strings.Split(matches[1], ".")
	segments := make([]int64, len(segmentsStr))
	for i, str := range segmentsStr {
		val, err := strconv.ParseInt(str, 10, 64)
		if err != nil {
			return nil, fmt.Errorf(
				"error parsing version: %s", err)
		}

		segments[i] = val
	}

	// Even though we could support more than three segments, if we
	// got less than three, pad it with 0s. This is to cover the basic
	// default usecase of semver, which is MAJOR.MINOR.PATCH at the minimum
	for i := len(segments); i < 3; i++ {
		segments = append(segments, 0)
	}

	pre := matches[7]
	if pre == "" {
		pre = matches[4]
	}

	return &Version{
		metadata: matches[10],
		pre:      pre,
		segments: segments,
		si:       len(segmentsStr),
		original: v,
	}, nil
}

// Compare compares this version to another version. This
// returns -1, 0, or 1 if this version is smaller, equal,
// or larger than the other version, respectively.
//
// If you want boolean results, use the LessThan, Equal,
// GreaterThan, GreaterThanOrEqual or LessThanOrEqual methods.
func (v *Version) Compare(other *Version) int {
	// A quick, efficient equality check
	if v.String() == other.String() {
		return 0
	}

	segmentsSelf := v.Segments64()
	segmentsOther := other.Segments64()

	// If the segments are the same, we must compare on prerelease info
	if reflect.DeepEqual(segmentsSelf, segmentsOther) {
		preSelf := v.Prerelease()
		preOther := other.Prerelease()
		if preSelf == "" && preOther == "" {
			return 0
		}
		if preSelf == "" {
			return 1
		}
		if preOther == "" {
			return -1
		}

		return comparePrereleases(preSelf, preOther)
	}

	// Get the highest specificity (hS), or if they're equal, just use
	// segmentSelf length
	lenSelf := len(segmentsSelf)
	lenOther := len(segmentsOther)
	hS := lenSelf
	if lenSelf < lenOther {
		hS = lenOther
	}
	// Compare the segments
	// Because a constraint could have more/less specificity than the version
	// it's
	// checking, we need to account for a lopsided or jagged comparison
	for i := 0; i < hS; i++ {
		if i > lenSelf-1 {
			// This means Self had the lower specificity
			// Check to see if the remaining segments in Other are all zeros
			if !allZero(segmentsOther[i:]) {
				// if not, it means that Other has to be greater than Self
				return -1
			}
			break
		} else if i > lenOther-1 {
			// this means Other had the lower specificity
			// Check to see if the remaining segments in Self are all zeros -
			if !allZero(segmentsSelf[i:]) {
				//if not, it means that Self has to be greater than Other
				return 1
			}
			break
		}
		lhs := segmentsSelf[i]
		rhs := segmentsOther[i]
		if lhs == rhs {
			continue
		} else if lhs < rhs {
			return -1
		}
		// Otherwis, rhs was > lhs, they're not equal
		return 1
	}

	// if we got this far, they're equal
	return 0
}

func allZero(segs []int64) bool {
	for _, s := range segs {
		if s != 0 {
			return false
		}
	}
	return true
}

func comparePart(preSelf string, preOther string) int {
	if preSelf == preOther {
		return 0
	}

	var selfInt int64
	selfNumeric := true
	selfInt, err := strconv.ParseInt(preSelf, 10, 64)
	if err != nil {
		selfNumeric = false
	}

	var otherInt int64
	otherNumeric := true
	otherInt, err = strconv.ParseInt(preOther, 10, 64)
	if err != nil {
		otherNumeric = false
	}

	// if a part is empty, we use the other to decide
	if preSelf == "" {
		if otherNumeric {
			return -1
		}
		return 1
	}

	if preOther == "" {
		if selfNumeric {
			return 1
		}
		return -1
	}

	if selfNumeric && !otherNumeric {
		return -1
	} else if !selfNumeric && otherNumeric {
		return 1
	} else if !selfNumeric && !otherNumeric && preSelf > preOther {
		return 1
	} else if selfInt > otherInt {
		return 1
	}

	return -1
}

func comparePrereleases(v string, other string) int {
	// the same pre release!
	if v == other {
		return 0
	}

	// split both pre releases for analyse their parts
	selfPreReleaseMeta := strings.Split(v, ".")
	otherPreReleaseMeta := strings.Split(other, ".")

	selfPreReleaseLen := len(selfPreReleaseMeta)
	otherPreReleaseLen := len(otherPreReleaseMeta)

	biggestLen := otherPreReleaseLen
	if selfPreReleaseLen > otherPreReleaseLen {
		biggestLen = selfPreReleaseLen
	}

	// loop for parts to find the first difference
	for i := 0; i < biggestLen; i = i + 1 {
		partSelfPre := ""
		if i < selfPreReleaseLen {
			partSelfPre = selfPreReleaseMeta[i]
		}

		partOtherPre := ""
		if i < otherPreReleaseLen {
			partOtherPre = otherPreReleaseMeta[i]
		}

		compare := comparePart(partSelfPre, partOtherPre)
		// if parts are equals, continue the loop
		if compare != 0 {
			return compare
		}
	}

	return 0
}

// GreaterThan tests if this version is greater than another version.
func (v *Version) GreaterThan(o *Version) bool {
	return v.Compare(o) > 0
}

// Prerelease returns any prerelease data that is part of the version,
// or blank if there is no prerelease data.
//
// Prerelease information is anything that comes after the "-" in the
// version (but before any metadata). For example, with "1.2.3-beta",
// the prerelease information is "beta".
func (v *Version) Prerelease() string {
	return v.pre
}

// Segments64 returns the numeric segments of the version as a slice of int64s.
//
// This excludes any metadata or pre-release information. For example,
// for a version "1.2.3-beta", segments will return a slice of
// 1, 2, 3.
func (v *Version) Segments64() []int64 {
	result := make([]int64, len(v.segments))
	copy(result, v.segments)
	return result
}

// String returns the full version string included pre-release
// and metadata information.
//
// This value is rebuilt according to the parsed segments and other
// information. Therefore, ambiguities in the version string such as
// prefixed zeroes (1.04.0 => 1.4.0), `v` prefix (v1.0.0 => 1.0.0), and
// missing parts (1.0 => 1.0.0) will be made into a canonicalized form
// as shown in the parenthesized examples.
func (v *Version) String() string {
	var buf bytes.Buffer
	fmtParts := make([]string, len(v.segments))
	for i, s := range v.segments {
		// We can ignore err here since we've pre-parsed the values in segments
		str := strconv.FormatInt(s, 10)
		fmtParts[i] = str
	}
	fmt.Fprint(&buf, strings.Join(fmtParts, "."))
	if v.pre != "" {
		fmt.Fprintf(&buf, "-%s", v.pre)
	}
	if v.metadata != "" {
		fmt.Fprintf(&buf, "+%s", v.metadata)
	}

	return buf.String()
}

// -------------- version ----------------

// -------------- mod --------------------

// Copy from golang.org/x/mod@v0.15.0/modfile/read.go.

var (
	slashSlash = []byte("//")
	moduleStr  = []byte("module")
)

// ModulePath returns the module path from the gomod file text.
// If it cannot find a module path, it returns an empty string.
// It is tolerant of unrelated problems in the go.mod file.
func ModulePath(mod []byte) string {
	for len(mod) > 0 {
		line := mod
		mod = nil
		if i := bytes.IndexByte(line, '\n'); i >= 0 {
			line, mod = line[:i], line[i+1:]
		}
		if i := bytes.Index(line, slashSlash); i >= 0 {
			line = line[:i]
		}
		line = bytes.TrimSpace(line)
		if !bytes.HasPrefix(line, moduleStr) {
			continue
		}
		line = line[len(moduleStr):]
		n := len(line)
		line = bytes.TrimSpace(line)
		if len(line) == n || len(line) == 0 {
			continue
		}

		if line[0] == '"' || line[0] == '`' {
			p, err := strconv.Unquote(string(line))
			if err != nil {
				return "" // malformed quoted string or multiline module path
			}
			return p
		}

		return string(line)
	}
	return "" // missing module path
}

func ModTidy(location string, envs []string, verbose bool) error {
	mod_file := path.Join(location, "go.mod")
	if !IsFilePresent(mod_file) {
		return fmt.Errorf("%s/go.mod does not exist", location)
	}

	if verbose {
		log.Printf("Run 'go mod tidy' on [%s].\n", location)
	}

	if err := ExecCmd([]string{"go", "mod", "tidy"}, location, envs, verbose); err != nil {
		return fmt.Errorf(
			"failed to execute 'go mod tidy' on [%s]. \n\t%w",
			location,
			err,
		)
	}

	return nil
}

func Generate(location string, envs []string, verbose bool) error {
	if verbose {
		log.Printf("Run 'go generate' on [%s].\n", location)
	}

	err := ExecCmd([]string{"go", "generate"}, location, envs, verbose)
	if err != nil {
		return fmt.Errorf(
			"failed to execute 'go generate' on [%s]. \n\t%w",
			location,
			err,
		)
	}

	return nil
}

func ModAddLocalModule(module *ExtensionModule, target string) error {
	// go mod edit -replace <mod>=<full path>
	//
	// Note that the module must be replaced with the full path, as the module
	// should be recognized when running 'go mod tidy' in <auto-gen> directory.
	err := ExecCmd(
		[]string{
			"go",
			"mod",
			"edit",
			"-replace",
			fmt.Sprintf(
				"%s=./addon/extension/%s",
				module.module,
				path.Base(module.location),
			),
		},
		target,
		nil,
		false,
	)
	if err != nil {
		return err
	}

	// go mod edit -require <mod>@<version>
	//
	// The version is a Go-generated pseudo-version number, which contains the
	// following three parts.
	//
	// - baseVersionPrefix (vX.0.0 or vX.Y.Z-0) is a value derived either from a
	// semantic version tag that precedes the revision or from vX.0.0 if there
	// is no such tag.
	//
	// - timestamp (yymmddhhmmss) is the UTC time the revision was created. In
	// Git, this is the commit time, not the author time.
	//
	// - revisionIdentifier (abcdefabcdef) is a 12-character prefix of the
	// commit hash, or in Subversion, a zero-padded revision number.
	//
	// TODO(Liu): auto generated the version based on the above rule.
	err = ExecCmd(
		[]string{
			"go",
			"mod",
			"edit",
			"-require",
			fmt.Sprintf("%s@v0.0.0-00010101000000-000000000000",
				module.module,
			),
		},
		target,
		nil,
		false,
	)

	return err
}

// -------------- mod --------------------

// -------------- options ----------------

const (
	DefaultAutoImportFile string = "generated_auto_import_addons.go"
)

type BuildOption struct {
	AppDir            string
	Verbose           bool
	AutoGenImportFile string
	KeepAutoGen       bool
	CleanAutoGen      bool

	// Same as the flags in 'go build'.
	Mod        string
	GCFlags    string
	LdFlags    string
	EnableAsan bool
}

func (b *BuildOption) Valid() error {
	return nil
}

// -------------- options ----------------

// -------------- builder ----------------

type AppBuilder struct {
	pkgName           string
	acquiredGoVersion string
	options           *BuildOption
	cachedEnv         map[string]string
	extensions        []*ExtensionModule
}

func NewAppBuilder(
	pkgName string,
	goVersion string,
	options *BuildOption,
) *AppBuilder {
	return &AppBuilder{
		pkgName:           pkgName,
		acquiredGoVersion: goVersion,
		options:           options,
		cachedEnv:         make(map[string]string),
		extensions:        make([]*ExtensionModule, 0),
	}
}

// runTidyAndGenerate executes 'go mod tidy' and 'go generate' on GO app and all
// GO extensions.
func (ab *AppBuilder) runTidyAndGenerate(envs []string) error {
	for _, ext := range ab.extensions {
		if err := ModTidy(ext.location, envs, ab.options.Verbose); err != nil {
			return err
		}

		if err := Generate(ext.location, envs, ab.options.Verbose); err != nil {
			return err
		}
	}

	if err := ModTidy(ab.options.AppDir, envs, ab.options.Verbose); err != nil {
		return err
	}

	if err := Generate(ab.options.AppDir, envs, ab.options.Verbose); err != nil {
		return err
	}

	return nil
}

func (ab *AppBuilder) buildGoApp(envs []string) error {
	// go build -o bin/<app> -v .
	cmdline := []string{
		"go",
		"build",
		"-o",
		fmt.Sprintf("bin/%s", ab.pkgName),
	}

	if ab.options.EnableAsan {
		cmdline = append(cmdline, "-asan")
	}

	if ab.options.Verbose {
		cmdline = append(cmdline, "-v")
	}

	// There are more than one source file in the app, as the auto-import file
	// has been generated.
	cmdline = append(cmdline, ".")

	log.Printf("Build GO app with command: %s\n", strings.Join(cmdline, " "))

	return ExecCmd(cmdline, ab.options.AppDir, envs, ab.options.Verbose)
}

func (ab *AppBuilder) Build() error {
	if err := ab.precheck(); err != nil {
		return fmt.Errorf("precheck failed. Root cause: \n\t%w", err)
	}

	if err := ab.autoDetectExtensions(); err != nil {
		return fmt.Errorf(
			"auto detect extensions failed. Root cause: \n\t%w",
			err,
		)
	}

	// Prepare the execution environments.
	ab.addPrivateRepo()
	ab.addRuntimeLdflags()
	// ab.autoDetectCompiler()

	// All commands will be executed with the environments.
	envs := ab.buildExecEnvs()

	if err := ab.runTidyAndGenerate(envs); err != nil {
		return err
	}

	if err := ab.generateAutoImportFile(); err != nil {
		return err
	}

	if err := ab.requireExtensionModules(); err != nil {
		return err
	}

	// Run 'go mod tidy' to sync the dependencies of the extensions.
	if err := ModTidy(ab.options.AppDir, envs, ab.options.Verbose); err != nil {
		return err
	}

	// Everything is ready, we can build the app.
	return ab.buildGoApp(envs)
}

func (ab *AppBuilder) Cleanup() {
	if err := ab.restoreGoModAndGoSum(); err != nil {
		log.Fatalf("%v\n", err)
	}

	autoGenImport := path.Join(ab.options.AppDir, ab.options.AutoGenImportFile)
	if IsFilePresent(autoGenImport) {
		err := os.Remove(autoGenImport)
		if err != nil {
			log.Fatalf("Failed to remove auto-gen file, %v\n", err)
		}
	}
}

// -------------- builder ----------------

// -------------- check ------------------

const (
	KeyCGOEnabled string = "CGO_ENABLED"
)

func (ab *AppBuilder) checkGoVersion() error {
	go_version := runtime.Version()
	if strings.HasPrefix(go_version, "go") {
		go_version = go_version[2:]
		v, _ := NewVersion(go_version)
		acquired, _ := NewVersion(ab.acquiredGoVersion)
		if acquired.GreaterThan(v) {
			return fmt.Errorf(
				"go version higher than %s is acquired, current is %s",
				ab.acquiredGoVersion,
				go_version,
			)
		}
	} else {
		return fmt.Errorf("not recognizable go version, %s", go_version)
	}

	if ab.options.Verbose {
		log.Printf("Go version [%s] is found.\n", go_version)
	}

	return nil
}

func (ab *AppBuilder) checkAppIntegrity() error {
	if len(ab.options.AppDir) == 0 {
		return errors.New("failed to detect GO app directory")
	}

	manifest, err := LoadManifest(ab.options.AppDir)
	if err != nil {
		return fmt.Errorf("%s is not a GO app, %w", ab.options.AppDir, err)
	}

	if err := manifest.IsGoApp(); err != nil {
		return fmt.Errorf("%s is not a GO app, %w", ab.options.AppDir, err)
	}

	if !IsDirPresent(path.Join(ab.options.AppDir, "scripts/build")) {
		return errors.New("invalid GO app, scripts/build is absent")
	}

	if ab.options.Verbose {
		log.Printf("Go app [%s] is found.\n", ab.options.AppDir)
	}

	return nil
}

func (ab *AppBuilder) checkCGOEnabled() error {
	if err := ab.getGoEnv(); err != nil {
		return fmt.Errorf("failed to execute 'go env' command. \n\t%w", err)
	}

	if enabled, ok := ab.cachedEnv[KeyCGOEnabled]; ok {
		if enabled != "1" {
			return errors.New("CGO is not enabled")
		}
	} else {
		// CGO is enabled by default at most platform. Refer to `cgoEnabled` map
		// in `cmd/dist/build.go`.
		if ab.options.Verbose {
			log.Printf("%s is not found, which is treated as enabled.\n", KeyCGOEnabled)
		}
	}

	return nil
}

func (ab *AppBuilder) precheck() error {
	if err := ab.checkGoVersion(); err != nil {
		return err
	}

	if err := ab.checkAppIntegrity(); err != nil {
		return err
	}

	if err := ab.checkCGOEnabled(); err != nil {
		return err
	}

	return nil
}

// -------------- check ------------------

// -------------- env --------------------

const (
	KeyGoPrivate     string = "GOPRIVATE"
	KeyGoNoProxy     string = "GONOPROXY"
	KeyGoNoSumdb     string = "GONOSUMDB"
	KeyCGOLdflags    string = "CGO_LDFLAGS"
	KeyCGOCflags     string = "CGO_CFLAGS"
	AgoraPrivateRepo string = "*.agoralab.co"
)

func (ab *AppBuilder) getGoEnv() error {
	if len(ab.cachedEnv) > 0 {
		return nil
	}

	cmd := exec.Command("go", "env", "-json")

	var stdout bytes.Buffer
	cmd.Stdout = &stdout

	if err := cmd.Run(); err != nil {
		return err
	}

	if err := json.Unmarshal(stdout.Bytes(), &ab.cachedEnv); err != nil {
		return err
	}

	return nil
}

// addPrivateRepo adds repositories owned in agoralab.co to private go modules.
//
// Note that when you execute command 'go env -w GOPRIVATE="*.agoralab.co"', the
// GONOPROXY and GONOSUMDB will be set to "*.agoralab.co" automatically. And you
// can not change GONOPROXY or GONOSUMDB without changing GOPRIVATE.
func (ab *AppBuilder) addPrivateRepo() {
	privates := ab.cachedEnv[KeyGoPrivate]
	if len(privates) == 0 {
		privates = AgoraPrivateRepo
	} else {
		if !strings.Contains(privates, AgoraPrivateRepo) {
			privates = privates + "," + AgoraPrivateRepo
		}
	}

	ab.cachedEnv[KeyGoPrivate] = privates

	// GONOPROXY and GONOSUMDB must be same as GOPRIVATE.
	ab.cachedEnv[KeyGoNoProxy] = privates
	ab.cachedEnv[KeyGoNoSumdb] = privates
}

// autoDetectCompiler chooses the C compiler (gcc or clang) to compile the cgo
// codes (auto generated by the cgo compiler, not the C codes in go binding).
//
// The final application executable will link rte_runtime_go.so, if asan is
// enabled in compiling rte_runtime_go.so, the C compiler must be same as the
// compiler used to compile rte_runtime_go.so.
//
// If there is any C/C++ extension in this GO app, and the compiler and flags
// (whether enables asan) must be same as the extension if the extension is
// compiled with asan. However, this is the job of the arpm when installing
// extensions, not this app builder.
func (ab *AppBuilder) autoDetectCompiler() {
	// TODO(Liu): auto detect the C compiler.
	ab.cachedEnv["CC"] = "clang"

	var cflags, ldflags string
	switch runtime.GOOS {
	case "linux":
		cflags = "-fsanitize=address -fsanitize=leak"
		ldflags = "-fsanitize=address -fsanitize=leak"
	case "darwin":
		cflags = "-fsanitize=address"
		ldflags = "-fsanitize=address"
	default:
		log.Fatalf("Unsupported platform %s.\n", runtime.GOOS)
	}

	cflags += " " + ab.cachedEnv[KeyCGOCflags]
	ab.cachedEnv[KeyCGOCflags] = cflags

	ldflags += " " + ab.cachedEnv[KeyCGOLdflags]
	ab.cachedEnv[KeyCGOLdflags] = ldflags
}

func (ab *AppBuilder) addRuntimeLdflags() {
	var flags string

	switch runtime.GOOS {
	case "linux":
		flags = "-Llib -lrte_runtime_go -Wl,-rpath=$ORIGIN/../lib"
	case "darwin":
		flags = "-Llib -lrte_runtime_go -Wl,-rpath,@loader_path/../lib"
	default:
		log.Fatalf("Unsupported platform %s.\n", runtime.GOOS)
	}

	_flags := ab.cachedEnv[KeyCGOLdflags]
	if len(_flags) > 0 {
		flags += " " + _flags
	}

	ab.cachedEnv[KeyCGOLdflags] = flags
}

// buildExecEnvs combines the OS environments and GO environments (i.e., go
// env) as the final execution environments.
func (ab *AppBuilder) buildExecEnvs() []string {
	envs := os.Environ()

	if ab.options.Verbose {
		log.Println("Go env:")
	}

	for k, v := range ab.cachedEnv {
		if ab.options.Verbose {
			log.Printf("\t%s='%s'\n", k, v)
		}

		envs = append(envs, k+"="+v)
	}

	return envs
}

// -------------- env --------------------

// -------------- extension --------------

type ExtensionModule struct {
	// The module name in go.mod
	module string

	location string
}

func (em *ExtensionModule) String() string {
	return fmt.Sprintf("%s @ %s", em.module, em.location)
}

func LoadExtensionModule(
	location string,
	verbose bool,
) (*ExtensionModule, error) {
	if !IsFilePresent(path.Join(location, "manifest.json")) {
		if verbose {
			log.Printf("%s is not an extension, no manifest.json.\n", location)
		}

		return nil, nil
	}

	if mf, err := LoadManifest(location); err != nil {
		return nil, err
	} else {
		if err := mf.IsGoExtension(); err != nil {
			if verbose {
				log.Printf("%s is not an extension, %v.\n", location, err)
			}

			return nil, nil
		}
	}

	modFile := path.Join(location, "go.mod")
	if !IsFilePresent(modFile) {
		return nil, fmt.Errorf("%s extension is invalid, no go.mod", location)
	}

	bytes, err := os.ReadFile(modFile)
	if err != nil {
		return nil, fmt.Errorf("%s extension is invalid. \n\t%w", location, err)
	}

	module := ModulePath(bytes)
	if len(module) == 0 {
		return nil, fmt.Errorf("no mod is detected in %s/go.mod", location)
	}

	return &ExtensionModule{
		module:   module,
		location: location,
	}, nil
}

func (ab *AppBuilder) autoDetectExtensions() error {
	extBaseDir := path.Join(ab.options.AppDir, "addon/extension")
	if !IsDirPresent(extBaseDir) {
		if ab.options.Verbose {
			log.Println(
				"The base directory [addon/extension] is absent, no extensions.",
			)
		}

		return nil
	}

	entries, err := os.ReadDir(extBaseDir)
	if err != nil {
		return err
	}

	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}

		extDir := path.Join(extBaseDir, entry.Name())
		ext, err := LoadExtensionModule(extDir, ab.options.Verbose)
		if err != nil {
			return err
		}

		if ext == nil {
			// Not an GO extension.
			continue
		}

		ab.extensions = append(ab.extensions, ext)
	}

	if ab.options.Verbose && len(ab.extensions) > 0 {
		log.Println("Go Extensions are detected:")
		for _, ext := range ab.extensions {
			log.Printf("\t%s\n", ext)
		}
	}

	return nil
}

// -------------- extension --------------

// -------------- manifest ---------------

type RtePackageManifest struct {
	Type     string `json:"type"`
	Language string `json:"language"`
}

func LoadManifest(pkgDir string) (*RtePackageManifest, error) {
	manifest := path.Join(pkgDir, "manifest.json")
	if !IsFilePresent(manifest) {
		return nil, fmt.Errorf("%s/manifest.json is absent", pkgDir)
	}

	if mf, err := os.ReadFile(manifest); err != nil {
		return nil, err
	} else {
		var manifest *RtePackageManifest
		if err := json.Unmarshal(mf, &manifest); err != nil {
			return nil, fmt.Errorf("%s/manifest.json is invalid. \n\t%w", pkgDir, err)
		} else {
			return manifest, nil
		}
	}
}

func (pm *RtePackageManifest) IsGoApp() error {
	if pm.Language != "go" {
		return fmt.Errorf(
			"the language in manifest.json is [%s]", pm.Language,
		)
	}

	if pm.Type != "app" {
		return fmt.Errorf(
			"the type in manifest.json is [%s]", pm.Type,
		)
	}

	return nil
}

func (pm *RtePackageManifest) IsGoExtension() error {
	if pm.Language != "go" {
		return fmt.Errorf(
			"the language in manifest.json is [%s]", pm.Language,
		)
	}

	if pm.Type != "extension" {
		return fmt.Errorf(
			"the type in manifest.json is [%s]", pm.Type,
		)
	}

	return nil
}

// -------------- manifest ---------------

// -------------- import -----------------

func (ab *AppBuilder) generateAutoImportFile() error {
	// The auto generated import file must be located in the app directory.
	importFile := path.Join(ab.options.AppDir, ab.options.AutoGenImportFile)
	if IsFilePresent(importFile) {
		if err := os.Remove(importFile); err != nil {
			return fmt.Errorf(
				"failed to remove auto-gen import file. \n\t%w",
				err,
			)
		}
	}

	if len(ab.extensions) == 0 {
		log.Println(
			"No extension is detected, no need to generate import file.",
		)

		return nil
	}

	f, err := os.Create(importFile)
	if err != nil {
		return fmt.Errorf("failed to create auto-gen import file. \n\t%w", err)
	}

	defer f.Close()

	_, _ = f.WriteString("// Code generated by app builder. DO NOT EDIT.\n\n")
	_, _ = f.WriteString(fmt.Sprintf("package %s\n\n", ab.pkgName))

	for _, ext := range ab.extensions {
		_, _ = f.WriteString(fmt.Sprintf("import _ \"%s\"\n", ext.module))
	}

	if ab.options.Verbose {
		log.Printf("Auto-import file is generated at [%s].", importFile)
	}

	return nil
}

func (ab *AppBuilder) requireExtensionModules() error {
	if len(ab.extensions) == 0 {
		log.Println(
			"No extension is detected, no need to require extension modules.",
		)

		return nil
	}

	// The go.mod will be modified to add the extension as go modules.
	// Therefore, we need to copy the original go.mod and go.sum as the backup,
	// and restore them after the build.

	err := CopyFile(
		path.Join(ab.options.AppDir, "go.mod"),
		path.Join(ab.options.AppDir, BackupGoMod),
	)
	if err != nil {
		return fmt.Errorf("failed to backup go.mod. \n\t%w", err)
	}

	originSum := path.Join(ab.options.AppDir, "go.sum")
	if IsFilePresent(originSum) {
		err = CopyFile(originSum, path.Join(ab.options.AppDir, BackupGoSum))
		if err != nil {
			return fmt.Errorf("failed to backup go.sum. \n\t%w", err)
		}
	}

	// Add GO extensions as the module of the app.
	for _, ext := range ab.extensions {
		if err := ModAddLocalModule(ext, ab.options.AppDir); err != nil {
			return fmt.Errorf(
				"failed to add %s as go module of the app. \n\t%w",
				ext.location,
				err,
			)
		}
	}

	if ab.options.Verbose {
		log.Println("Add extension modules to app successfully.")
	}

	return nil
}

func (ab *AppBuilder) restoreGoModAndGoSum() error {
	backupMod := path.Join(ab.options.AppDir, BackupGoMod)
	originMod := path.Join(ab.options.AppDir, "go.mod")
	if IsFilePresent(backupMod) {
		if err := os.Remove(originMod); err != nil {
			return fmt.Errorf("failed to restore go.mod. \n\t%w", err)
		}

		if err := MoveFile(backupMod, originMod); err != nil {
			return fmt.Errorf("failed to restore go.mod. \n\t%w", err)
		}
	}

	backupSum := path.Join(ab.options.AppDir, BackupGoSum)
	originSum := path.Join(ab.options.AppDir, "go.sum")
	if IsFilePresent(backupSum) {
		if err := os.Remove(originSum); err != nil {
			return fmt.Errorf("failed to restore go.sum. \n\t%w", err)
		}

		if err := MoveFile(backupSum, originSum); err != nil {
			return fmt.Errorf("failed to restore go.sum. \n\t%w", err)
		}

	}

	return nil
}

// -------------- import -----------------

// -------------- io ---------------------

func MkdirIfAbsent(path string) error {
	if stat, err := os.Stat(path); err == nil {
		// Present.
		if stat.IsDir() {
			return nil
		} else {
			return fmt.Errorf("%s is present, but not a directory", path)
		}
	}

	return os.MkdirAll(path, os.FileMode(0775).Perm())
}

func CopyFile(src string, dest string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}

	defer in.Close()

	if _, err := os.Stat(dest); err == nil {
		return fmt.Errorf("%s is already present", dest)
	}

	out, err := os.Create(dest)
	if err != nil {
		return err
	}

	defer out.Close()

	_, err = io.Copy(out, in)
	return err
}

func MoveFile(src string, dest string) error {
	if err := CopyFile(src, dest); err != nil {
		return err
	}

	return os.Remove(src)
}

func IsFilePresent(path string) bool {
	if stat, err := os.Stat(path); err == nil {
		return !stat.IsDir()
	}

	return false
}

func IsDirPresent(path string) bool {
	if stat, err := os.Stat(path); err == nil {
		return stat.IsDir()
	}

	return false
}

// -------------- io ---------------------

// -------------- cmdline ----------------

func ExecCmd(cmdline []string, cwd string, envs []string, verbose bool) error {
	name := cmdline[0]
	var args []string
	if len(cmdline) > 1 {
		args = cmdline[1:]
	}

	cmd := exec.Command(name, args...)

	if len(cwd) > 0 {
		cmd.Dir = cwd
	}

	if len(envs) > 0 {
		cmd.Env = envs
	}

	var stdoutScanner, stderrScanner *bufio.Scanner

	if stdout, err := cmd.StdoutPipe(); err != nil {
		return err
	} else {
		stdoutScanner = bufio.NewScanner(stdout)
	}

	if stderr, err := cmd.StderrPipe(); err != nil {
		return err
	} else {
		stderrScanner = bufio.NewScanner(stderr)
	}

	if err := cmd.Start(); err != nil {
		return err
	}

	for stderrScanner.Scan() {
		log.Printf("\t%s\n", stderrScanner.Text())
	}

	if verbose {
		done := make(chan struct{}, 1)
		go func() {
			for stdoutScanner.Scan() {
				log.Printf("\t%s\n", stdoutScanner.Text())
			}
			done <- struct{}{}
		}()
		<-done
	}

	err := stdoutScanner.Err()
	if err == nil {
		err = stderrScanner.Err()
	}

	if err != nil {
		_ = cmd.Process.Kill()
		_ = cmd.Wait()
		return err
	}

	return cmd.Wait()
}

// -------------- cmdline ----------------
