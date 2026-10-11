import 'dart:io';
import 'dart:typed_data' as typed;
import 'package:flutter/services.dart';

class NativeBridge {
  static const channel = MethodChannel('lifeos/native');
  bool get supported => Platform.isAndroid;
  Future<Map<String, Object?>> diagnostics({Map<String,String>? labels}) async => supported
    ? Map<String, Object?>.from(await channel.invokeMapMethod<String, Object?>('diagnostics', labels) ?? {})
    : {'supported': false, 'zone': 'UTC'};
  Future<void> reconcile(List<Map<String, Object?>> entries) async {
    if (supported) await channel.invokeMethod<void>('reconcile', {'entries': entries});
  }
  Future<List<Map<String, Object?>>> pendingActions() async => supported
    ? [for (final raw in await channel.invokeListMethod<Object?>('pendingActions') ?? []) Map<String, Object?>.from(raw as Map)] : [];
  Future<void> acknowledge(List<String> ids) async {
    if (supported) await channel.invokeMethod<void>('ackActions', ids);
  }
  Future<String?> launchTarget() async => supported ? channel.invokeMethod<String>('launchTarget') : null;
  Future<void> request(String permission) async {
    if (supported) await channel.invokeMethod<void>(permission);
  }
  Future<void> testNotification(Map<String, Object?> labels) async {
    if (!supported) throw PlatformException(code: 'unsupported');
    await channel.invokeMethod<void>('testNotification', labels);
  }
  Future<bool> saveBackup(typed.Uint8List bytes) async {
    if (!supported) throw PlatformException(code: 'unsupported');
    return await channel.invokeMethod<bool>('saveBackup', bytes) ?? false;
  }
  Future<typed.Uint8List?> readBackup() async {
    if (!supported) throw PlatformException(code: 'unsupported');
    return channel.invokeMethod<typed.Uint8List>('readBackup');
  }
}
