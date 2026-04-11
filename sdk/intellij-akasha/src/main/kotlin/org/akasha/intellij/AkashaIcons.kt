package org.akasha.intellij

import com.intellij.openapi.util.IconLoader

/**
 * Centralized icon loader. Keep the lookup path stable — every reference to
 * the Akasha file icon flows through here so re-theming is a single-file edit.
 */
object AkashaIcons {
    @JvmField
    val FILE = IconLoader.getIcon("/icons/akasha.svg", AkashaIcons::class.java)
}
