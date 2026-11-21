/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05572(unsigned int count)
{
    const unsigned int limit = 112u;
    return count > limit ? limit : count;
}
