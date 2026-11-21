/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00218(unsigned int count)
{
    const unsigned int limit = 228u;
    return count > limit ? limit : count;
}
