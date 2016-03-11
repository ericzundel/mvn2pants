# Tests for code in squarepants/src/main/python/squarepants/junit_report.py
#
# Run with:
# ./pants test squarepants/src/test/python/squarepants_test:junit_report
from __future__ import unicode_literals

import json
import os
import tempfile
import shutil
import sys
import unittest

from squarepants import junit_report

class TestJUnitReportParse(unittest.TestCase):

  def test_all_success(self):
    suite = """
    <foo>
    <testsuite xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="https://maven.apache.org/surefire/maven-surefire-plugin/xsd/surefire-test-report.xsd" name="com.squareup.crypto.pssr.PssrTest" time="0.684" tests="6" errors="0" skipped="0" failures="0">
    <testcase name="testTamperedSignatureCausesFailure" classname="com.squareup.crypto.pssr.PssrTest" time="0.001"/>
    <testcase name="testSignAndEncodeThenVerifyAndRecover" classname="com.squareup.crypto.pssr.PssrTest" time="0.224"/>
    <testcase name="testSignAndEncodeThenVerifyAndRecoverWithCorruptedUnrecoverableData" classname="com.squareup.crypto.pssr.PssrTest" time="0"/>
    <testcase name="testMessageSizeBoundaries" classname="com.squareup.crypto.pssr.PssrTest" time="0"/>
    <testcase name="testSignAndEncodeThenVerifyAndRecoverWithUnrecoverableData" classname="com.squareup.crypto.pssr.PssrTest" time="0.001"/>
    <testcase name="testSignAndEncodeWithTestVectors" classname="com.squareup.crypto.pssr.PssrTest" time="0.001"/>
    </testsuite>
    </foo>
    """
    lst = list(junit_report.parse_string(suite))
    self.assertEquals(len(lst), 6)
    for elem in lst:
        self.assertEquals(elem.state, junit_report.State.SUCCESS)
        self.assertLess(elem.time, 0.3)
    self.assertEquals(lst[0].full_name, 'com.squareup.crypto.pssr.PssrTest.testTamperedSignatureCausesFailure')
    self.assertEquals(lst[1].full_name, 'com.squareup.crypto.pssr.PssrTest.testSignAndEncodeThenVerifyAndRecover')
    self.assertEquals(lst[2].full_name, 'com.squareup.crypto.pssr.PssrTest.testSignAndEncodeThenVerifyAndRecoverWithCorruptedUnrecoverableData')
    self.assertEquals(lst[3].full_name, 'com.squareup.crypto.pssr.PssrTest.testMessageSizeBoundaries')
    self.assertEquals(lst[4].full_name, 'com.squareup.crypto.pssr.PssrTest.testSignAndEncodeThenVerifyAndRecoverWithUnrecoverableData')
    self.assertEquals(lst[5].full_name, 'com.squareup.crypto.pssr.PssrTest.testSignAndEncodeWithTestVectors')
    self.assertEquals(lst[1].time, 0.224)

  def test_one_failure(self):
    suite = """
    <foo>
    <testsuite xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="https://maven.apache.org/surefire/maven-surefire-plugin/xsd/surefire-test-report.xsd" name="com.squareup.crypto.PrivateKeysTest" time="0.191" tests="3" errors="1" skipped="0" failures="0">
    <testcase name="keyDecryptFailsWithWrongPassword" classname="com.squareup.crypto.PrivateKeysTest" time="0.066"/>
    <testcase name="canDecodeEncryptedKey" classname="com.squareup.crypto.PrivateKeysTest" time="0.012">
    java.lang.RuntimeException: org.bouncycastle.openssl.PEMException: Unable to create OpenSSL PBDKF: PBKDF-OpenSSL SecretKeyFactory not available at com.google.common.base.Throwables.propagate(Throwables.java:160) at com.squareup.crypto.PrivateKeys.fromPem(PrivateKeys.java:63) at com.squareup.crypto.PrivateKeysTest.canDecodeEncryptedKey(PrivateKeysTest.java:73) at sun.reflect.NativeMethodAccessorImpl.invoke0(Native Method) at sun.reflect.NativeMethodAccessorImpl.invoke(NativeMethodAccessorImpl.java:57) at sun.reflect.DelegatingMethodAccessorImpl.invoke(DelegatingMethodAccessorImpl.java:43) at java.lang.reflect.Method.invoke(Method.java:606) at org.junit.runners.model.FrameworkMethod$1.runReflectiveCall(FrameworkMethod.java:50) at org.junit.internal.runners.model.ReflectiveCallable.run(ReflectiveCallable.java:12) at org.junit.runners.model.FrameworkMethod.invokeExplosively(FrameworkMethod.java:47) at org.junit.internal.runners.statements.InvokeMethod.evaluate(InvokeMethod.java:17) at org.junit.runners.ParentRunner.runLeaf(ParentRunner.java:325) at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:78) at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:57) at org.junit.runners.ParentRunner$3.run(ParentRunner.java:290) at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:71) at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:288) at org.junit.runners.ParentRunner.access$000(ParentRunner.java:58) at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:268) at org.junit.runners.ParentRunner.run(ParentRunner.java:363) at org.junit.runners.Suite.runChild(Suite.java:128) at org.junit.runners.Suite.runChild(Suite.java:27) at org.junit.runners.ParentRunner$3.run(ParentRunner.java:290) at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:71) at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:288) at org.junit.runners.ParentRunner.access$000(ParentRunner.java:58) at org.junit.runners.ParentRunner$2.evaluate(ParentRunner.java:268) at org.junit.runners.ParentRunner.run(ParentRunner.java:363) at org.apache.maven.surefire.junitcore.JUnitCore.run(JUnitCore.java:55) at org.apache.maven.surefire.junitcore.JUnitCoreWrapper.createRequestAndRun(JUnitCoreWrapper.java:130) at org.apache.maven.surefire.junitcore.JUnitCoreWrapper.executeEager(JUnitCoreWrapper.java:101) at org.apache.maven.surefire.junitcore.JUnitCoreWrapper.execute(JUnitCoreWrapper.java:77) at org.apache.maven.surefire.junitcore.JUnitCoreProvider.invoke(JUnitCoreProvider.java:177) at org.apache.maven.surefire.booter.ForkedBooter.invokeProviderInSameClassLoader(ForkedBooter.java:286) at org.apache.maven.surefire.booter.ForkedBooter.runSuitesInProcess(ForkedBooter.java:240) at org.apache.maven.surefire.booter.ForkedBooter.main(ForkedBooter.java:121) Caused by: org.bouncycastle.openssl.PEMException: Unable to create OpenSSL PBDKF: PBKDF-OpenSSL SecretKeyFactory not available at org.bouncycastle.openssl.jcajce.PEMUtilities.getKey(Unknown Source) at org.bouncycastle.openssl.jcajce.PEMUtilities.crypt(Unknown Source) at org.bouncycastle.openssl.jcajce.JcePEMDecryptorProviderBuilder$1$1.decrypt(Unknown Source) at org.bouncycastle.openssl.PEMEncryptedKeyPair.decryptKeyPair(Unknown Source) at com.squareup.crypto.PrivateKeys.fromPem(PrivateKeys.java:60) ... 34 more Caused by: java.security.NoSuchAlgorithmException: PBKDF-OpenSSL SecretKeyFactory not available at javax.crypto.SecretKeyFactory.init(SecretKeyFactory.java:121) at javax.crypto.SecretKeyFactory.getInstance(SecretKeyFactory.java:159) at org.bouncycastle.jcajce.util.DefaultJcaJceHelper.createSecretKeyFactory(Unknown Source) ... 39 more
    </testcase>
    <testcase name="pemEncodeDecodeIsSymmetric" classname="com.squareup.crypto.PrivateKeysTest" time="0.104"/>
    </testsuite>
    </foo>
    """
    lst = list(junit_report.parse_string(suite))
    self.assertEquals(len(lst), 3)
    self.assertEquals(lst[1].state, junit_report.State.FAILURE)
    self.assertEquals(lst[0].state, junit_report.State.SUCCESS)
    self.assertEquals(lst[2].state, junit_report.State.SUCCESS)

  def test_hidden_error(self):
    suite = """
    <foo>
    <testsuite xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="https://maven.apache.org/surefire/maven-surefire-plugin/xsd/surefire-test-report.xsd" name="com.squareup.crypto.pssr.PssrTest" time="0.684" tests="6" errors="1" skipped="0" failures="0">
    <testcase name="testTamperedSignatureCausesFailure" classname="com.squareup.crypto.pssr.PssrTest" time="0.001"/>
    <testcase name="testSignAndEncodeThenVerifyAndRecover" classname="com.squareup.crypto.pssr.PssrTest" time="0.224"/>
    <testcase name="testSignAndEncodeThenVerifyAndRecoverWithCorruptedUnrecoverableData" classname="com.squareup.crypto.pssr.PssrTest" time="0"/>
    <testcase name="testMessageSizeBoundaries" classname="com.squareup.crypto.pssr.PssrTest" time="0"/>
    <testcase name="testSignAndEncodeThenVerifyAndRecoverWithUnrecoverableData" classname="com.squareup.crypto.pssr.PssrTest" time="0.001"/>
    <testcase name="testSignAndEncodeWithTestVectors" classname="com.squareup.crypto.pssr.PssrTest" time="0.001"/>
    </testsuite>
    </foo>
    """
    lst = list(junit_report.parse_string(suite))
    self.assertEquals(len(lst), 7)
    for i in range(6):
        self.assertEquals(lst[i].state, junit_report.State.SUCCESS)
    self.assertEquals(lst[6].state, junit_report.State.FAILURE)
    self.assertEquals(lst[6].full_name, 'com.squareup.crypto.pssr.PssrTest.DUMMY_TEST')

  def test_hidden_failure(self):
    suite = """
    <foo>
    <testsuite xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="https://maven.apache.org/surefire/maven-surefire-plugin/xsd/surefire-test-report.xsd" name="com.squareup.crypto.pssr.PssrTest" time="0.684" tests="6" errors="0" skipped="0" failures="1">
    <testcase name="testTamperedSignatureCausesFailure" classname="com.squareup.crypto.pssr.PssrTest" time="0.001"/>
    <testcase name="testSignAndEncodeThenVerifyAndRecover" classname="com.squareup.crypto.pssr.PssrTest" time="0.224"/>
    <testcase name="testSignAndEncodeThenVerifyAndRecoverWithCorruptedUnrecoverableData" classname="com.squareup.crypto.pssr.PssrTest" time="0"/>
    <testcase name="testMessageSizeBoundaries" classname="com.squareup.crypto.pssr.PssrTest" time="0"/>
    <testcase name="testSignAndEncodeThenVerifyAndRecoverWithUnrecoverableData" classname="com.squareup.crypto.pssr.PssrTest" time="0.001"/>
    <testcase name="testSignAndEncodeWithTestVectors" classname="com.squareup.crypto.pssr.PssrTest" time="0.001"/>
    </testsuite>
    </foo>
    """
    lst = list(junit_report.parse_string(suite))
    self.assertEquals(len(lst), 7)
    for i in range(6):
        self.assertEquals(lst[i].state, junit_report.State.SUCCESS)
    self.assertEquals(lst[6].state, junit_report.State.FAILURE)
    self.assertEquals(lst[6].full_name, 'com.squareup.crypto.pssr.PssrTest.DUMMY_TEST')

  def test_realistic_failure(self):
    suite = """
    <testsuite errors="0" failures="1" name="com.squareup.activity.collector.ActivityCollectorAcceptanceTest" tests="3" time="4.083678">
    <testcase classname="com.squareup.activity.collector.ActivityCollectorAcceptanceTest" name="test2" time="1.037436">
        <failure message="Actual and expected have the same elements but not in the same order, at index 0 actual element was:"
                type="java.lang.AssertionError">java.lang.AssertionError:
        at org.pantsbuild.tools.junit.ConsoleRunner.main(ConsoleRunner.java:12)
    </failure>
    </testcase>
    </testsuite>
    """
    lst = list(junit_report.parse_string(suite))
    self.assertEquals(len(lst), 1)
    self.assertEquals(lst[0].state, junit_report.State.FAILURE)

  def test_alien_failure(self):
    suite = """
    <testsuite errors="0" failures="1" name="com.squareup.activity.collector.ActivityCollectorAcceptanceTest" tests="3" time="4.083678">
    <testcase classname="com.squareup.activity.collector.ActivityCollectorAcceptanceTest" name="test2" time="1.037436">
        <boomboom><foo>The eagle has left the nest. Repeat, the eagle has left the nest.</foo></boomboom>
    </testcase>
    </testsuite>
    """
    lst = list(junit_report.parse_string(suite))
    self.assertEquals(len(lst), 1)
    self.assertEquals(lst[0].state, junit_report.State.FAILURE)

  def test_missing_time_field(self):
    suite = """
    <testsuite errors="0" failures="1" name="com.squareup.activity.collector.ActivityCollectorAcceptanceTest" tests="3" time="4.083678">
    <testcase classname="com.squareup.activity.collector.ActivityCollectorAcceptanceTest" name="test2">
        <failure message="Actual and expected have the same elements but not in the same order, at index 0 actual element was:"
                type="java.lang.AssertionError">java.lang.AssertionError:
        at org.pantsbuild.tools.junit.ConsoleRunner.main(ConsoleRunner.java:12)
    </failure>
    </testcase>
    </testsuite>
    """
    lst = list(junit_report.parse_string(suite))
    self.assertEquals(len(lst), 1)
    self.assertEquals(lst[0].state, junit_report.State.FAILURE)

  def test_malformed_time_field(self):
    suite = """
    <testsuite errors="0" failures="1" name="com.squareup.activity.collector.ActivityCollectorAcceptanceTest" tests="3" time="4.083678">
    <testcase classname="com.squareup.activity.collector.ActivityCollectorAcceptanceTest" name="test2" time="potato">
        <failure message="Actual and expected have the same elements but not in the same order, at index 0 actual element was:"
                type="java.lang.AssertionError">java.lang.AssertionError:
        at org.pantsbuild.tools.junit.ConsoleRunner.main(ConsoleRunner.java:12)
    </failure>
    </testcase>
    </testsuite>
    """
    lst = list(junit_report.parse_string(suite))
    self.assertEquals(len(lst), 1)
    self.assertEquals(lst[0].state, junit_report.State.FAILURE)


class TestRFC7464Record(unittest.TestCase):

    @staticmethod
    def decode(s):
        return json.loads(s[1:-1].decode('utf-8'))

    def test_success(self):
        case = junit_report.TestCase(full_name='foo.bar', time=1.3, state=junit_report.State.SUCCESS)
        res = junit_report.rfc7464_record_from_case(case)
        self.assertEquals(res[0], b'\x1e')
        self.assertEquals(res[-1], b'\n')
        dct = self.decode(res)
        self.assertEquals(dct.pop('time'), 1.3)
        self.assertEquals(dct.pop('state'), 'success')
        self.assertEquals(dct.pop('full-name'), 'foo.bar')

    def test_success_with_unicode(self):
        case = junit_report.TestCase(full_name='foo\u2603bar', time=1.3, state=junit_report.State.SUCCESS)
        res = junit_report.rfc7464_record_from_case(case)
        self.assertEquals(res[0], b'\x1e')
        self.assertEquals(res[-1], b'\n')
        dct = self.decode(res)
        self.assertEquals(dct.pop('time'), 1.3)
        self.assertEquals(dct.pop('state'), 'success')
        self.assertEquals(dct.pop('full-name'), 'foo\u2603bar', 'Go away, Anna!')

    def test_failure(self):
        case = junit_report.TestCase(full_name='foo\u2603bar', time=1.3, state=junit_report.State.FAILURE)
        res = junit_report.rfc7464_record_from_case(case)
        self.assertEquals(res[0], b'\x1e')
        self.assertEquals(res[-1], b'\n')
        dct = self.decode(res)
        self.assertEquals(dct.pop('time'), 1.3)
        self.assertEquals(dct.pop('state'), 'failure')
        self.assertEquals(dct.pop('full-name'), 'foo\u2603bar', 'Go away, Anna!')


class TestFindTrueFailures(unittest.TestCase):

    exc = ValueError('hello there')

    @staticmethod
    def is_flake(name):
        return name.startswith('flake.')

    def test_empty_failures(self):
        cases = []
        with self.assertRaises(ValueError):
            junit_report.find_true_failures(self.is_flake, cases, self.exc)

    def test_no_failures(self):
        cases = [junit_report.TestCase(full_name='foo\u2603bar', time=1.3, state=junit_report.State.SUCCESS)]
        with self.assertRaises(ValueError):
            junit_report.find_true_failures(self.is_flake, cases, self.exc)

    def test_flake_only(self):
        cases = [junit_report.TestCase(full_name='flake.foo.bar', time=1.3, state=junit_report.State.FAILURE)]
        junit_report.find_true_failures(self.is_flake, cases, self.exc)

    def test_failure(self):
        cases = [junit_report.TestCase(full_name='foo.bar', time=1.3, state=junit_report.State.FAILURE)]
        with self.assertRaises(ValueError):
            junit_report.find_true_failures(self.is_flake, cases, self.exc)

    def test_flake_and_failure(self):
        cases = [junit_report.TestCase(full_name='flake.foo.bar', time=1.3, state=junit_report.State.FAILURE),
                 junit_report.TestCase(full_name='foo.bar', time=1.3, state=junit_report.State.FAILURE)]
        with self.assertRaises(ValueError):
            junit_report.find_true_failures(self.is_flake, cases, self.exc)


class TestParser(unittest.TestCase):

    def setUp(self):
        self.args = ['--output=output', '--dir=dir', '--flakes=flakes']

    def test_good(self):
        ns = junit_report.PARSER.parse_args(self.args)
        self.assertEquals(ns.output, 'output')
        self.assertEquals(ns.dir, 'dir')
        self.assertEquals(ns.flakes, 'flakes')

    def test_missing(self):
        for el in self.args:
            args = self.args[:]
            args.remove(el)
            with self.assertRaises(SystemExit):
                junit_report.PARSER.parse_args(args)


class TestUtility(unittest.TestCase):

    def test_compose(self):
        a = lambda x: x + 1
        b = lambda x: x * 2
        self.assertEquals(junit_report.compose(a, b)(5), 11)

    def test_flow_and_process(self):
        lst = []
        it = junit_report.flow_and_process(lst.append, [1, 2])
        self.assertEquals(next(it), 1)
        self.assertEquals(lst, [1])
        self.assertEquals(next(it), 2)
        self.assertEquals(lst, [1, 2])
        with self.assertRaises(StopIteration):
           next(it)

GOOD_XML="""
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<testsuite errors="0" failures="0" hostname="moshez-mac15.local" name="com.squareup.pants.PantsTestAppTest" tests="1" time="0.008724" timestamp="2015-10-16T21:52:32">
    <system-err></system-err>
    <system-out></system-out>
    <properties>
        <property name="java.runtime.name" value="Java(TM) SE Runtime Environment"/>
        <property name="sun.boot.library.path" value="/Library/Java/JavaVirtualMachines/jdk1.8.0_45.jdk/Contents/Home/jre/lib"/>
        <property name="java.vm.version" value="25.45-b02"/>
        <property name="gopherProxySet" value="false"/>
        <property name="java.vm.vendor" value="Oracle Corporation"/>
        <property name="java.vendor.url" value="http://java.oracle.com/"/>
        <property name="path.separator" value=":"/>
        <property name="java.vm.name" value="Java HotSpot(TM) 64-Bit Server VM"/>
        <property name="file.encoding.pkg" value="sun.io"/>
        <property name="user.country" value="US"/>
        <property name="sun.java.launcher" value="SUN_STANDARD"/>
        <property name="sun.os.patch.level" value="unknown"/>
        <property name="java.vm.specification.name" value="Java Virtual Machine Specification"/>
        <property name="user.dir" value="/Users/moshez/Development/java/squarepants/pants-test-app"/>
        <property name="java.runtime.version" value="1.8.0_45-b14"/>
        <property name="java.awt.graphicsenv" value="sun.awt.CGraphicsEnvironment"/>
        <property name="java.endorsed.dirs" value="/Library/Java/JavaVirtualMachines/jdk1.8.0_45.jdk/Contents/Home/jre/lib/endorsed"/>
        <property name="os.arch" value="x86_64"/>
        <property name="java.io.tmpdir" value="/var/folders/qs/n9bm0z4s4h747_6760xqhtbm0002xg/T/"/>
        <property name="line.separator" value="
"/>
        <property name="java.vm.specification.vendor" value="Oracle Corporation"/>
        <property name="os.name" value="Mac OS X"/>
        <property name="sun.jnu.encoding" value="UTF-8"/>
        <property name="java.library.path" value="/Users/moshez/Library/Java/Extensions:/Library/Java/Extensions:/Network/Library/Java/Extensions:/System/Library/Java/Extensions:/usr/lib/java:."/>
        <property name="java.specification.name" value="Java Platform API Specification"/>
        <property name="java.class.version" value="52.0"/>
        <property name="sun.management.compiler" value="HotSpot 64-Bit Tiered Compilers"/>
        <property name="os.version" value="10.10.5"/>
        <property name="http.nonProxyHosts" value="local|*.local|169.254/16|*.169.254/16"/>
        <property name="user.home" value="/Users/moshez"/>
        <property name="user.timezone" value="UTC"/>
        <property name="java.awt.printerjob" value="sun.lwawt.macosx.CPrinterJob"/>
        <property name="file.encoding" value="UTF-8"/>
        <property name="java.specification.version" value="1.8"/>
        <property name="java.class.path" value="../../.pants.d/bootstrap/bootstrap-jvm-tools/tool_cache/shaded_jars/org.pantsbuild.tools.junit.ConsoleRunner-872da3ff30d7d94ddd83962eae3fe0707dc0687c-ShadedToolFingerprintStrategy_b30a23e6795b.jar:../../.pants.d/resources/services/bf21a9e8fbc5a3846fb05b4fa0859e0917b2202f-JvmServiceFingerprintStrategy_b30a23e6795b:../../.pants.d/compile/jvm/zinc/jars/98de2223f3ac.jar:../../.pants.d/compile/jvm/zinc/jars/781accd68900.jar:../../.pants.d/ivy/jars/com.google.inject/guice/jars/guice-4.0.jar:../../.pants.d/ivy/jars/aopalliance/aopalliance/jars/aopalliance-1.0.jar:../../.pants.d/ivy/jars/javax.inject/javax.inject/jars/javax.inject-1.jar:../../.pants.d/ivy/jars/junit/junit/jars/junit-4.12.jar:../../.pants.d/ivy/jars/org.hamcrest/hamcrest-core/jars/hamcrest-core-1.3.jar:../../.pants.d/compile/jvm/zinc/jars/84a41a68357d.jar:../../.pants.d/compile/jvm/zinc/jars/af4ab7dcbe6c.jar:../../.pants.d/resources/prepare/ed3ec11cbadfa922ca5dfefcd2962c0bc5dbdd9f-TaskIdentityFingerprintStrategy_b30a23e6795b:../../.pants.d/compile/jvm/zinc/jars/66ac911a2308.jar"/>
        <property name="user.name" value="moshez"/>
        <property name="java.vm.specification.version" value="1.8"/>
        <property name="sun.java.command" value="org.pantsbuild.tools.junit.ConsoleRunner -suppress-output -outdir /Users/moshez/Development/java/.pants.d/test/junit -per-test-timer -parallel-threads 0 com.squareup.pants.PantsTestAppTest -xmlreport"/>
        <property name="java.home" value="/Library/Java/JavaVirtualMachines/jdk1.8.0_45.jdk/Contents/Home/jre"/>
        <property name="sun.arch.data.model" value="64"/>
        <property name="user.language" value="en"/>
        <property name="java.specification.vendor" value="Oracle Corporation"/>
        <property name="awt.toolkit" value="sun.lwawt.macosx.LWCToolkit"/>
        <property name="java.vm.info" value="mixed mode"/>
        <property name="java.version" value="1.8.0_45"/>
        <property name="java.ext.dirs" value="/Users/moshez/Library/Java/Extensions:/Library/Java/JavaVirtualMachines/jdk1.8.0_45.jdk/Contents/Home/jre/lib/ext:/Library/Java/Extensions:/Network/Library/Java/Extensions:/System/Library/Java/Extensions:/usr/lib/java"/>
        <property name="sun.boot.class.path" value="/Library/Java/JavaVirtualMachines/jdk1.8.0_45.jdk/Contents/Home/jre/lib/resources.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_45.jdk/Contents/Home/jre/lib/rt.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_45.jdk/Contents/Home/jre/lib/sunrsasign.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_45.jdk/Contents/Home/jre/lib/jsse.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_45.jdk/Contents/Home/jre/lib/jce.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_45.jdk/Contents/Home/jre/lib/charsets.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_45.jdk/Contents/Home/jre/lib/jfr.jar:/Library/Java/JavaVirtualMachines/jdk1.8.0_45.jdk/Contents/Home/jre/classes"/>
        <property name="java.awt.headless" value="true"/>
        <property name="java.vendor" value="Oracle Corporation"/>
        <property name="file.separator" value="/"/>
        <property name="java.vendor.url.bug" value="http://bugreport.sun.com/bugreport/"/>
        <property name="sun.io.unicode.encoding" value="UnicodeBig"/>
        <property name="sun.cpu.endian" value="little"/>
        <property name="socksNonProxyHosts" value="local|*.local|169.254/16|*.169.254/16"/>
        <property name="ftp.nonProxyHosts" value="local|*.local|169.254/16|*.169.254/16"/>
        <property name="sun.cpu.isalist" value=""/>
    </properties>
    <testcase classname="com.squareup.pants.PantsTestAppTest" name="test" time="0.006753"/>
</testsuite>
"""

# Note: the integration tests only test failures.
# The reason for their existence is that while not properly ignoring a flake is annoying,
# it merely leads to a bad developer experience. Ignoring a failing test leads to problematic
# master, so for that we go a step beyond the unit tests, and back ourselves up with
# integration tests.
class TestIntegration(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir)
        self.flakes = os.path.join(self.tmpdir, 'flakes')
        self.reports = os.path.join(self.tmpdir, 'reports')
        self.output = os.path.join(self.tmpdir, 'output')
        os.mkdir(self.flakes)
        args = ['meeeeeeeeee!',
                '--output=' + self.output,
                '--dir=' + self.reports,
                '--flakes' + self.flakes]
        def resetArgv(oldArgs):
            self.argv = oldArgs
        self.addCleanup(resetArgv, sys.argv)
        self.argv = args

    def test_no_directory(self):
        with self.assertRaises(SystemExit):
            junit_report.main()

    def test_empty_directory(self):
        os.mkdir(self.reports)
        with self.assertRaises(SystemExit):
            junit_report.main()

    def test_directory_with_success(self):
        os.mkdir(self.reports)
        with open(os.path.join(self.reports, 'foo.xml'), 'w') as fp:
            fp.write(GOOD_XML)
        with self.assertRaises(SystemExit):
            junit_report.main()

    def test_directory_with_failure(self):
        os.mkdir(self.reports)
        bad_xml = GOOD_XML.replace('errors="0"', 'errors="1"')
        with open(os.path.join(self.reports, 'foo.xml'), 'w') as fp:
            fp.write(bad_xml)
        with self.assertRaises(SystemExit):
            junit_report.main()

    def test_directory_with_failure_and_some_other_flake(self):
        with open(os.path.join(self.flakes, 'my.test'), 'w') as fp:
            fp.write("Heeeeere's Johnny!")
        os.mkdir(self.reports)
        bad_xml = GOOD_XML.replace('errors="0"', 'errors="1"')
        with open(os.path.join(self.reports, 'foo.xml'), 'w') as fp:
            fp.write(bad_xml)
        with self.assertRaises(SystemExit):
            junit_report.main()
