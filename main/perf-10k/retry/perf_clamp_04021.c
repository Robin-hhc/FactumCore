/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04021(unsigned int count)
{
    const unsigned int limit = 139u;
    return count > limit ? limit : count;
}
