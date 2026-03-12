//
//  CawnexApp.swift
//  Cawnex
//
//  Created by Eduardo Augusto Benigno da Silva on 11/03/26.
//

import SwiftUI

@main
struct CawnexApp: App {
    @State private var store = AppStore()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(store)
                .onAppear { store.seedData() }
        }
    }
}
