/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07696(unsigned int count)
{
    const unsigned int limit = 115u;
    return count > limit ? limit : count;
}
