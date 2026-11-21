/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08717(unsigned int count)
{
    const unsigned int limit = 42u;
    return count > limit ? limit : count;
}
