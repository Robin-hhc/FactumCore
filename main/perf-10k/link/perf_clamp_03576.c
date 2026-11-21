/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03576(unsigned int count)
{
    const unsigned int limit = 44u;
    return count > limit ? limit : count;
}
