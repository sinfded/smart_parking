<script setup lang="ts">
definePageMeta({ layout: false })

const client = useSupabaseClient()
const email = ref("")
const password = ref("")
const error = ref("")
const loading = ref(false)

async function signIn() {
  error.value = ""
  loading.value = true
  const { error: authError } = await client.auth.signInWithPassword({
    email: email.value,
    password: password.value,
  })
  loading.value = false
  if (authError) {
    error.value = authError.message
    return
  }
  await navigateTo("/")
}
</script>

<template>
  <div class="bg-background flex min-h-svh items-center justify-center p-6">
    <div class="w-full max-w-sm space-y-6">
      <div class="space-y-1 text-center">
        <h1 class="text-2xl font-semibold tracking-tight">Smart Parking</h1>
        <p class="text-muted-foreground text-sm">Sign in to your admin account</p>
      </div>

      <Card>
        <CardContent class="pt-6">
          <form class="space-y-4" @submit.prevent="signIn">
            <div class="space-y-2">
              <Label for="email">Email</Label>
              <Input
                id="email"
                v-model="email"
                type="email"
                placeholder="you@example.com"
                required
                autocomplete="email"
              />
            </div>
            <div class="space-y-2">
              <Label for="password">Password</Label>
              <Input
                id="password"
                v-model="password"
                type="password"
                placeholder="••••••••"
                required
                autocomplete="current-password"
              />
            </div>
            <Alert v-if="error" variant="destructive">
              <AlertDescription>{{ error }}</AlertDescription>
            </Alert>
            <Button type="submit" class="w-full" :disabled="loading">
              <Spinner v-if="loading" class="mr-2 size-4" />
              Sign in
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
