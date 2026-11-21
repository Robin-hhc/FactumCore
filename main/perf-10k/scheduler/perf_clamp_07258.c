/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07258(unsigned int count)
{
    const unsigned int limit = 139u;
    return count > limit ? limit : count;
}
